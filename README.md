# For-Shikisaigakkai-Experiment
This repository is made for an experiment. 
Arduino IDEを開きボードをArduino UNO、ポートはCOM9(Macだと名前が変わります)を選択してください。Arduino IDEの上部にあるツール→ライブラリを管理　から、FASTLEDというライブラリをインストールしてください。
Aruduino UNOにLEDの赤を5Vに、白を~6に、黒をGNDに接続してください。USB A to BケーブルでパソコンとArduinoを接続したら書き込みを行ってください(Arduino IDEの → のボタン)。
pythonをインストールします。おそらくバージョンは何でもいいですが私はpython3.12.7を使って実行できました。
windowsではコマンドプロンプト、Macでならターミナルを開き、python -m pip install pyserial　というコマンドを実行します。
その後 shikisai_experiment.pyを実行します(コマンドでpyhon {ファイルのパス}　か　エクスプローラーからpythonを選択して実行してください)
きっといけるはずです。
