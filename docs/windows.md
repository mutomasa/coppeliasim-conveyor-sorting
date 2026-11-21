# Windows 11 でのセットアップ

CoppeliaSim は Windows 側で動かし、Python は Docker Desktop（WSL 2 / Linux コンテナ）の中で動かします。

1. **WSL 2 を有効にする**：管理者の PowerShell で `wsl --install` を実行し、再起動する。
2. **Docker Desktop をインストールする**：https://www.docker.com/products/docker-desktop/
   - Settings → General で「Use the WSL 2 based engine」を ON にする。
   - 右下のアイコンが「Engine running」になるまで待つ。
3. **Git for Windows をインストールする**：https://git-scm.com/download/win
4. **CoppeliaSim 4.10（Edu）をインストールする**：https://www.coppeliarobotics.com/
5. **ファイアウォール**：CoppeliaSim の初回起動時に「アクセスを許可する」を選ぶ。
   Docker からの接続（ポート 23000）がブロックされると、接続確認がタイムアウトします。
6. PowerShell でリポジトリを取得してビルドする：

   ```powershell
   git clone <このリポジトリの URL>
   cd coppeliasim-conveyor-sorting
   docker compose build
   ```

7. CoppeliaSim を起動し、空のシーンのまま（シミュレーション停止中）にして、接続を確認する：

   ```powershell
   docker compose run --rm lab python src/check_connection.py
   docker compose run --rm lab python src/main.py
   ```

## うまくいかないとき

| 症状 | 対処 |
|---|---|
| `check_connection.py` が止まったまま | CoppeliaSim が起動しているか、ファイアウォールでポート 23000 が許可されているか確認する |
| `docker: command not found` | Docker Desktop を起動し直す。PowerShell を開き直す |
| `Cannot connect to the Docker daemon` | Docker Desktop が「Engine running」になってから実行する |
