# MOSS Dynamic Prompt 仕様書

## 登録と依存関係

登録IDは `MOSSDynamicPrompt`、カテゴリは `MOSS/Prompts`。抽選、Balanced履歴、JSON補強は内部モジュールとして同梱する。ComfyUIのTextGenerateとRegexReplaceを利用する。Python依存関係はrequirements.txtとpyproject.tomlに定義する。

## 入出力

A・B・C、ワイルドカードのルート、生成方式、seed、Balancedと履歴リセット、補強方式、画像サイズ、TEXT／JSONの設定を受け取る。補強用CLIPはLLMを使用する方式だけで要求する遅延入力。設定プリセットは任意入力。

出力順は最終プロンプトのリスト、補強ステータスのリスト、対応する履歴JSONのリスト、プロンプト件数。既存ワークフローの出力番号を維持する。

## 補強方式

OFFはA・Bのみを展開する。TEXTはCを補強し、A・Bと結合して展開する。customでTEXT補強をOFFにした場合は代替文を使う。JSONはA・Bと展開済みCの組合せからJSONを生成する。TEXT_JSONは元のCと補強済みCをJSON生成へ渡す。JSONは構造と座標を検証し、一度だけ修復を試す。

Thinkingのみの出力で最終文が空なら、ThinkingをOFFにして一度再試行する。TEXTの空の最終文を検出したら、画像生成へ渡す前にエラーを返す。

## プリセット

UI初期値はrecommended。TEXTのC補強を有効化し、TEXT 1024トークン／温度0.7、JSON 4096トークン／温度0.3、Thinking OFFを実行時に適用する。TEXTはTop-K 64、Top-P 0.95、Min-P 0.05、反復ペナルティ1.05、存在ペナルティ0、MTP OFF。付属システムプロンプトと既定チャットテンプレートを使用する。

customだけ詳細を表示し、選択した補強方式の設定だけを有効な操作対象にする。接続済みの詳細入力は接続を維持する。APIでプリセットを省略した場合はcustomを使用する。

## 抽選と性能

randomのBalancedはコレクションごとの独立した履歴を使い、ネスト展開はDynamic Prompts本体に委譲する。all_combinationsは候補ソートとシャッフルを無効化し、TXT／YAMLの定義順を保持する。

YAMLの解析結果から候補と行番号を取得し、二重解析を省く。LibYAML対応環境ではCSafeLoaderを使う。永続キャッシュを追加せず、次の展開時にファイル変更を読み込む。

履歴のJSON形式は既存のmoss_wildcard_trace v1を維持する。保存処理と専用ビューアーは、このノードとは別の連携先が担当する。
