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
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.groq.stt import GroqSTTService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

from config import GROQ_API_KEY, GROQ_MODEL, GROQ_WHISPER_MODEL
from core.database import add_message
from features.conversation import build_system_prompt


async def run_voice_bot(webrtc_connection, conversation_id, resident):
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
    stt = GroqSTTService(
        api_key=GROQ_API_KEY, settings=GroqSTTService.Settings(model=GROQ_WHISPER_MODEL)
    )
    llm = GroqLLMService(
        api_key=GROQ_API_KEY, settings=GroqLLMService.Settings(model=GROQ_MODEL)
    )

    context = LLMContext([{"role": "system", "content": build_system_prompt(resident)}])
    context_aggregator = LLMContextAggregatorPair(context)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            context_aggregator.assistant(),
            transport.output(),
        ]
    )
    task = PipelineTask(pipeline)

    @context_aggregator.user().event_handler("on_user_turn_stopped")
    async def on_user_turn_stopped(_aggregator, message):
        add_message(conversation_id, "user", message.content)
        webrtc_connection.send_app_message({"role": "user", "text": message.content})

    @context_aggregator.assistant().event_handler("on_assistant_turn_stopped")
    async def on_assistant_turn_stopped(_aggregator, message):
        add_message(conversation_id, "assistant", message.content)
        webrtc_connection.send_app_message({"role": "assistant", "text": message.content})

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client):
        await task.cancel()

    await PipelineRunner(handle_sigint=False).run(task)
