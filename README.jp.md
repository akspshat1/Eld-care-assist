*[English](README.md)*

# 高齢者施設向け 会話×記録自動化AI

入居者と会話するAIチャットボットが、会話内容から自動で介護記録・申し送りレポートを生成するアプリです。

## 機能

1. **Conversation** — 入居者ペルソナとの会話（テキスト入力・録音による音声入力・ボタン操作なしのハンズフリー音声通話〈Next.js UIのみ〉）。会話ごとに気分・要約・特記事項をAIが自動抽出してDBに保存。
2. **申し送りレポート生成** — 1日分の会話ログから次の介護士向けレポートを自動生成。
3. **Voice Reminders** — 服薬・水分補給・体操などの音声リマインダー。

## UIについて

同じSQLite DBとPythonバックエンドロジックを共有する、2種類のフロントエンドがあります。

- **Next.js**（`web/`） + **FastAPI**（`api/`） — メインのUI。マイク入力・音声読み上げはすべてブラウザ側で行うため、フロントエンドとバックエンドが別マシンでも動作します。会話ページには、Pipecatを使ったハンズフリー音声通話モード（WebRTC、発話ごとのボタン操作不要）もあります。
- **Streamlit**（`app.py`, `pages/`） — よりシンプルな単一プロセス構成のフォールバック。音声読み上げはサーバーと同じマシン上でpyttsx3（オフラインTTS）を使います。

## 技術スタック

- Python 3.11+（両UI共通のバックエンドロジック）
- LLM: GroqCloud API（`groq` SDK, モデル: `llama-3.3-70b-versatile`）
- 音声入力(STT): GroqCloud Whisper API（`whisper-large-v3-turbo`）
- DB: [ChromaDB](https://www.trychroma.com/)（`chromadb`, ローカル永続クライアント）。将来的に会話履歴をRAG的に検索活用できるようにするため採用
- 音声合成（Streamlitのみ）: pyttsx3（オフライン）
- リマインダー管理（Streamlitのみ）: `schedule`
- API: FastAPI + uvicorn
- フロントエンド: Next.js（TypeScript, App Router, Tailwind CSS）。マイク入力は`MediaRecorder`、音声読み上げはブラウザの`speechSynthesis`を使用
- ハンズフリー音声通話（Next.jsのみ）: [Pipecat](https://github.com/pipecat-ai/pipecat)（`pipecat-ai`）。`SmallWebRTCTransport`によりブラウザ↔バックエンド間を直接WebRTC接続（サードパーティのクラウド契約は不要）、発話区切りの検出はSilero VAD、STT・LLMはどちらもGroqを使用。専用のTTSプロバイダは使わず、確定したテキストをWebRTCのデータチャネル経由でブラウザに送り、他の機能と同じ`speechSynthesis`で読み上げる構成

LLM・TTS・DBはいずれも `core/` 配下の薄いラッパー経由で呼び出しており、実装を差し替えても機能側のコードは変更不要です。

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env
# .env を開いて GROQ_API_KEY を設定する

cd web
npm install
cp .env.local.example .env.local
# バックエンドが別ホストの場合は NEXT_PUBLIC_API_BASE_URL を編集する
```

## 起動

**Next.js + FastAPI**（メイン）:

```bash
# ターミナル1（プロジェクトルートで）
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# ターミナル2
cd web
npm run dev
```

`http://localhost:3000` を開いてください。`localhost`以外のアドレスでフロントエンドを開く場合、ブラウザはHTTPSでない限りマイクアクセスをブロックします（録音による音声入力・ハンズフリー音声通話の両方に影響します。音声読み上げ`speechSynthesis`は影響を受けません）。ハンズフリー音声通話はP2PのWebRTCのため、フロントエンドとバックエンドが同一ネットワーク上で到達可能である必要があります（別ネットワーク間のNAT越え用のTURNサーバーは用意していません）。

ハンズフリー音声通話は初回利用時にSilero VADモデル（小さいローカルモデル、初回のみ）をダウンロードします。また、DB（ChromaDB）もアプリの初回起動時にローカル埋め込みモデル（約80MB、初回のみ）をダウンロードします。

**Streamlit**（フォールバック）:

```bash
streamlit run app.py
```

起動後、DBのテーブルが作成されていること・`GROQ_API_KEY` が読み込まれていることが画面に表示されます。

## ディレクトリ構成

```
Eld-care-assist/
├── app.py                       # Streamlitの入口（セットアップ状況の確認）
├── config.py                    # .env読み込み・共通設定
├── core/                        # 技術スタックの差し替え可能な土台
│   ├── database.py                # ChromaDBコレクション管理・CRUD
│   ├── llm_client.py               # LLM(Groq)呼び出しラッパー
│   ├── tts_client.py                # TTS(pyttsx3)呼び出しラッパー
│   └── voice_pipeline.py            # Pipecatによるハンズフリー音声通話パイプライン
├── features/                    # 機能ごとのロジック（画面には依存しない）
│   ├── conversation.py             # ペルソナ用プロンプト生成・AI応答取得
│   ├── extraction.py                # 会話ログから気分・要約・特記事項を抽出
│   ├── report.py                     # 申し送りレポート生成
│   └── reminders.py                   # リマインダーのスケジュール管理
├── personas/personas.json       # 入居者ペルソナ定義
├── api/                          # Next.js用FastAPIバックエンド
│   └── main.py
├── web/                          # Next.jsフロントエンド
│   ├── lib/api.ts                  # fetchラッパー
│   ├── lib/webrtc.ts                # ハンズフリー通話: WebRTCシグナリング + データチャネル
│   └── app/
│       ├── conversation/page.tsx
│       ├── reports/page.tsx
│       └── reminders/page.tsx
├── pages/                       # Streamlitの各機能画面
│   ├── 1_会話.py
│   ├── 2_申し送りレポート.py
│   └── 3_リマインダー.py
└── data/                        # ChromaDBの永続ストア（Git管理外）
```

## 開発の進め方（実装済み）

1. 雛形（ディレクトリ構成・requirements.txt・.env管理・SQLiteテーブル設計）
2. Conversation機能（チャットUI + DB保存）
3. 会話ログからの自動抽出（気分・要約・特記事項）
4. 申し送りレポート生成
5. Voice Reminders
6. 音声入力(Groq Whisper)・入居者ペルソナの追加機能をStreamlit UIに追加
7. Next.js + FastAPI UIをStreamlitと並行して追加（会話のテキスト/音声入力・応答読み上げ、申し送りレポート、ポーリング方式の音声リマインダー）
8. Conversation機能にハンズフリー音声通話を追加（Pipecat + `SmallWebRTCTransport`、STT/LLMはGroq、応答はWebRTCのデータチャネル経由でブラウザの`speechSynthesis`が読み上げ）。既存のテキスト/録音方式と並行して利用可能
9. DBをSQLiteからChromaDBに移行（`core/database.py`を全面書き換え、公開関数のシグネチャは変更なし。他ファイルの変更は不要）。将来の会話履歴RAG活用を見据えた対応
