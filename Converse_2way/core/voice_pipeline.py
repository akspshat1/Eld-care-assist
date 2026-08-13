"""Hands-free voice conversation pipeline, built with Pipecat.

Wires the browser's WebRTC audio straight into Groq (STT + LLM), using
Pipecat's VAD-driven turn detection so the resident never has to press a
button to talk. There is no TTS stage here: Piper has no Japanese voice, so
the finalized assistant text is pushed to the browser over the WebRTC data
channel and read aloud there via the existing Web Speech API (same
speechSynthesis() call already used by the text/recorded-audio flows).

Feature code / the API layer should only call run_voice_bot() below.
"""
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair

# Pipecat 1.x needs the VAD analyzer on the user aggregator as well as on the
# transport: without it no VADController is built, so no "speech stopped" event
# ever fires, the user's turn never ends and nothing they say is sent.
# Pipecat 0.x has no such parameter and detects turns from the transport alone,
# so this is feature-detected rather than assumed.
try:
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMUserAggregatorParams,
    )
    _USER_PARAMS_TAKE_VAD = "vad_analyzer" in getattr(
        LLMUserAggregatorParams, "__dataclass_fields__", {})
except ImportError:                           # pipecat 0.x
    LLMUserAggregatorParams = None
    _USER_PARAMS_TAKE_VAD = False
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.groq.stt import GroqSTTService
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

from config import GROQ_API_KEY, GROQ_MODEL, GROQ_WHISPER_MODEL
from core.database import add_message
from features.conversation import build_system_prompt

# Optional recording of each spoken user turn. Pipecat's own
# AudioBufferProcessor raises on_user_turn_audio_data with the raw PCM when a
# turn ends, which is what makes voice-emotion analysis possible afterwards.
try:
    from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
except ImportError:                           # older pipecat
    AudioBufferProcessor = None

# A host app can set this to keep the audio of each user turn:
#   audio_sink(conversation_id, pcm_bytes, sample_rate)
# It is called straight after the turn's text has been stored, so the app can
# attach the recording to the message it just wrote.
audio_sink = None


async def run_voice_bot(webrtc_connection, conversation_id, resident, lang="ja"):
    """Run one hands-free call for a conversation until the browser hangs up.

    Every finalized user/assistant turn is saved to the DB via add_message
    (so extraction/report keep working unchanged) and also sent to the
    browser over the WebRTC data channel as {"role": ..., "text": ...} for
    live transcript display and speechSynthesis playback.
    """
    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=False,
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )
    # Without an explicit language this service defaults to English, so a
    # Japanese call was being transcribed as English.
    stt = GroqSTTService(
        api_key=GROQ_API_KEY,
        settings=GroqSTTService.Settings(
            model=GROQ_WHISPER_MODEL,
            language=Language.EN if lang == "en" else Language.JA,
        ),
    )
    llm = GroqLLMService(
        api_key=GROQ_API_KEY, settings=GroqLLMService.Settings(model=GROQ_MODEL)
    )

    context = LLMContext(
        [{"role": "system", "content": build_system_prompt(resident, lang)}]
    )
    if _USER_PARAMS_TAKE_VAD:
        # Its own analyzer instance: the transport's is already consuming that
        # audio stream, and VAD analyzers hold per-stream state.
        context_aggregator = LLMContextAggregatorPair(
            context,
            user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
        )
    else:
        context_aggregator = LLMContextAggregatorPair(context)

    # Sits right after the transport so it sees the incoming audio and the
    # VAD's UserStoppedSpeakingFrame that closes each turn.
    recorder = None
    if AudioBufferProcessor is not None and audio_sink is not None:
        recorder = AudioBufferProcessor(num_channels=1)

    stages = [transport.input()]
    if recorder is not None:
        stages.append(recorder)
    stages += [
        stt,
        context_aggregator.user(),
        llm,
        context_aggregator.assistant(),
        transport.output(),
    ]
    pipeline = Pipeline(stages)
    task = PipelineTask(pipeline)

    # The audio for a turn arrives before its transcript (VAD closes the turn,
    # then STT finishes), so it is held here and attached once the text lands.
    pending_audio = {"pcm": None, "rate": 0}

    if recorder is not None:
        @recorder.event_handler("on_user_turn_audio_data")
        async def on_user_turn_audio(_processor, audio, sample_rate, _channels):
            if audio:
                pending_audio["pcm"] = bytes(audio)
                pending_audio["rate"] = sample_rate

    def _emit(role, content):
        """Save a finalized turn and mirror it to the browser transcript.

        Empty aggregations do happen (a turn that produced no transcript), and
        sending those is what put blank bubbles in the transcript.
        """
        text = (content or "").strip()
        if not text:
            return
        add_message(conversation_id, role, text)
        webrtc_connection.send_app_message({"role": role, "text": text})

    # Note the signatures differ: the user handler is called with
    # (aggregator, strategy, message) while the assistant one gets
    # (aggregator, message). Taking only two args here meant `message` was
    # really the strategy object, so the user's own words never appeared.
    @context_aggregator.user().event_handler("on_user_turn_stopped")
    async def on_user_turn_stopped(_aggregator, _strategy, message):
        _emit("user", message.content)
        if audio_sink and pending_audio["pcm"] and (message.content or "").strip():
            try:
                audio_sink(conversation_id, pending_audio["pcm"],
                           pending_audio["rate"])
            except Exception:                 # noqa: BLE001 - never break the call
                pass
        pending_audio["pcm"] = None

    @context_aggregator.assistant().event_handler("on_assistant_turn_stopped")
    async def on_assistant_turn_stopped(_aggregator, message):
        _emit("assistant", message.content)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_transport, _client):
        """Speak first, so the resident is greeted instead of facing silence.

        Without this the pipeline waits for the user to talk, which leaves an
        older person staring at a screen wondering whether it is working.
        LLMRunFrame asks the LLM for a turn using the system prompt alone.
        """
        if recorder is not None:
            await recorder.start_recording()
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client):
        await task.cancel()

    await PipelineRunner(handle_sigint=False).run(task)
