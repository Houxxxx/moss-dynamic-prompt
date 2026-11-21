# MOSS Dynamic Prompt

ComfyUIでワイルドカード展開、Balanced抽選、TEXT／JSON補強をまとめて使うノードです。

## インストール・更新

1. ComfyUI Managerの **Install via Git URL** に `https://github.com/Houxxxx/moss-dynamic-prompt` を指定します。手動配置の場合はリポジトリを `ComfyUI/custom_nodes/moss-dynamic-prompt` に置き、ComfyUIのPythonで `python -m pip install -r custom_nodes/moss-dynamic-prompt/requirements.txt` を実行します。
2. ComfyUIを再起動し、ブラウザを再読み込みします。
3. ノード検索で **MOSS Dynamic Prompt** を追加し、ワイルドカードフォルダを指定します。

更新時はManagerまたはGitで更新して再起動してください。同じ登録名のノードは一つだけ配置します。このパッケージに抽選処理とJSON補強処理を同梱しています。ワイルドカード素材とモデルは利用者が用意します。

## 基本操作

A・B欄に固定プロンプトやワイルドカード、C欄に補強したいシーンを入力します。補強用CLIP、画像サイズ、seedを接続します。最終プロンプトを画像生成経路へ、補強ステータスをプレビューへ接続します。

| 補強方式 | 動作 |
| --- | --- |
| OFF | A・Bを展開する |
| TEXT | Cを英語のシーン文へ補強してA・Bと結合する |
| JSON | A・B・Cから構造化JSONを生成する |
| TEXT_JSON | CをTEXT補強したあと、A・Bと合わせてJSON化する |

LLMを使う方式では、テキスト生成に対応したCLIPが必要です。

## 推奨プリセットと詳細設定

`recommended` が新規ノードの初期値です。補強方式に合う値を自動適用し、詳細設定を隠します。`custom` に切り替えると、その方式で使用する設定だけが表示されます。TEXTのみならTEXT設定、JSONのみならJSON設定、TEXT_JSONなら両方を表示します。

| 推奨値 | TEXT | JSON |
| --- | --- | --- |
| 最大トークン数 | 1024 | 4096 |
| 温度 | 0.7 | 0.3 |
| Thinking | OFF | OFF |

TEXTはTop-K 64、Top-P 0.95、Min-P 0.05、反復ペナルティ1.05、存在ペナルティ0、MTP OFF、既定のチャットテンプレートを使用します。付属のシステムプロンプトを使い、推奨値は実行側でも適用します。

カスタムではTEXTのC補強を手動でOFFにして代替文を使えます。カスタム値は非表示中も保持します。既存APIで `settings_preset` を省略した場合は従来の手動設定を使います。

Thinkingだけで上限に達し最終文が空の場合は、ThinkingをOFFにして一度再試行します。TEXTの最終文が空のままなら、設定変更を案内するエラーを返します。ステータスで補強件数と再試行回数を確認できます。

## ワイルドカードと順序

- `random` はランダム抽選。BalancedをONにすると、解決済みコレクションごとに一巡まで同じ候補を再使用しません。
- `all_combinations` は全組合せ。TXTの行順とYAMLリストの順序を維持し、BalancedのON／OFFによる順序変更はありません。
- 履歴リセット間隔 `-1` はコレクションごとの一巡。正数NはN回の展開後に対象履歴をリセットします。リセット番号を変えると次回の展開でリセットします。
- YAMLの候補と行番号を一度の解析で取得します。PyYAMLがLibYAML対応なら高速なCSafeLoaderを使います。ファイルの追加・変更は次の展開時に読み込みます。

## 抽選履歴

出力は最終プロンプト、補強ステータス、ワイルドカード履歴、プロンプト総数です。対応するImage Saverに履歴を接続すると、PNGの `moss_wildcard_trace` に参照ファイルと行番号を保存できます。Image Saver側の対応が必要です。

## 開発時の確認

`python -m unittest discover -s tests -v` で、単体登録、推奨モード、空の補強出力の再試行、全組合せのファイル順、Balanced履歴を確認できます。LLMはテスト用の代替実装を使用します。

Comfy Registryへの公開は別途Publisher登録と公開設定が必要です。
