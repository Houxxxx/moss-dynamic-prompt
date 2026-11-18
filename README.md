# MOSS Dynamic Prompt

ローカルのワイルドカードをランダムまたは全組み合わせで展開するComfyUIノードです。Balanced、TEXTとJSON補強、プロンプト数と履歴の出力に対応します。

## インストール

1. ComfyUI Managerで **Install via Git URL** を開き、このパッケージを置いたGitリポジトリのURLを入れます。リポジトリ直下に `__init__.py` と `requirements.txt` を置いてください。
2. ComfyUIを再起動し、ノード追加メニューで **MOSS Dynamic Prompt** を検索します。
3. ノードで自分のワイルドカードフォルダを指定します。既存の同名ノードを手動配置している場合は重複しないよう一方だけを有効にしてください。

ComfyUI 0.42.1のAPIで検証しています。旧 `moss-local-prompts` と `moss-json-enhancer` の別途導入は不要です。ワイルドカード素材、モデル、V5の個人用ワークフローは含みません。V5全体を開く場合は、V5で使用する他のノードとモデルも用意してください。

## 使い方

A/B/Cと共有シードを設定し、展開方式を `random` または `all_combinations` にします。Balancedはランダムモードで利用できます。履歴リセット番号を変えると履歴をリセットできます。

`TEXT` でTEXT補強がオフの場合は「C｜TEXT補強オフ時の文」を使います。LLMを使う経路では補強用CLIPを接続します。「最終プロンプト」を正のCLIPエンコードへ接続します。対応するImage Saverには「ワイルドカード履歴」も接続できます。

## Managerの一覧に公開する

1. このフォルダを独立したGitHubリポジトリとして公開します。公開前にREADME、ソース、ライセンス方針を確認し、実際のURLを `pyproject.toml` の `Repository` に入れてください。
2. [Comfy Registry](https://registry.comfy.org/) にログインし、Publisherを作ります。実際のPublisher IDを `pyproject.toml` に設定します。
3. Registryで発行した公開用APIキーを使い、コミット済みのリポジトリ直下で `comfy node publish` を実行します。APIキーはGitに入れないでください。
4. 公開後にManagerの **Custom Nodes Manager** を開き、`MOSS Dynamic Prompt` または `moss-dynamic-prompt` を検索します。古い一覧が表示される場合は **DB: Channel (remote)** で取り直します。

[Registry公式公開ガイド](https://docs.comfy.org/registry/publishing) · [ComfyUI-Manager公式ガイド](https://github.com/Comfy-Org/ComfyUI-Manager)
