# git 履歴からのシークレット削除の検証

[English](README.en.md)

このリポジトリは、**git の履歴からシークレットを削除する手順**（git filter-repo で書き換えて force push する方法）を、ダミーのデータで実際に動かして検証した記録です。

- リポジトリの中身、ブランチ、PR、コミットの作者、シークレットの値は、**すべて検証のために作ったダミー**です。実在の組織、サービス、人物の情報は含みません。
- ダミーのシークレットは、実在のサービスの形式を使わず、架空の形式（`FAKESECRET_...`、`fakekey-...`、`FAKEPW-...` など）で作りました。
- このリポジトリの履歴は、検証のために何度も書き換えています。

## 結論

元の手順書のままでは、途中で止まるか、値を消し残しました。修正版の手順では、ブランチとタグから値を消し切り、コミット数やマージの構造などのリリースフローも保てました。ただし、GitHub 上の古いコミットや、マージ済みの PR の参照は、git の操作だけでは消せません。詳しくはレポートを読んでください。

## ファイルの案内

| パス | 内容 |
|---|---|
| [report/verification-report.ja.md](report/verification-report.ja.md) | 検証レポート（結論、確認項目 1〜17、よくある懸念への回答、確認できなかったこと） |
| [report/runbook-revised.ja.md](report/runbook-revised.ja.md) | 修正版の手順書（事前準備、実行、確認、事後対応、切り戻し、完了の条件） |
| [report/developer-notice.ja.md](report/developer-notice.ja.md) | 開発者向け案内文の雛形 |
| `scripts/setup/` | 検証用リポジトリの中身を作るスクリプト |
| `scripts/baseline/` | 書き換え前後の記録を取るスクリプト、古いクローンを作るスクリプト |
| `scripts/purge/` | 元の手順書を1ステップずつ実行するスクリプト、修正版の手順、保護の退避と復元、切り戻し |
| `scripts/verify/` | 値の直接検索、URL の確認、前後の比較、大きなリポジトリでの時間計測 |
| `scripts/gitleaks/gitleaks.toml` | 架空の形式を検出する gitleaks のルール |

アプリのファイル（`app/`、`config/`、`tests/` など）は、検証用のダミーです。

## 再実行の方法

### 必要なもの

- Git 2.40 以上、git filter-repo 2.47 以上、gitleaks 8.24 以上、GitHub CLI（`gh`。対象リポジトリの管理者権限でログイン）、Python 3、jq
- SSH で push できること

### 注意

- スクリプトは、作業ディレクトリ（既定は `~/purge-verify-work`）にダミーの値の一覧 `planted.json` を作ります。**このファイルはコミットも push もしないでください。**
- スクリプトは、コミットの作者にダミーの名前と `noreply` のアドレスを使い、`GIT_CONFIG_GLOBAL=/dev/null` で個人の git の設定を読まないようにしています。
- 対象のリポジトリは、環境変数 `REPO`（`owner/name`）で変えられます。**書き換えて困らないリポジトリでだけ**実行してください。

### 手順

```bash
# 1. build the sandbox (fresh random fake values every run) and set up GitHub
python3 scripts/setup/build_sandbox.py --workdir ~/purge-verify-work
scripts/setup/github_setup.sh ~/purge-verify-work      # push, PRs, Release, protection
scripts/setup/make_submodule_parent.sh                  # local-only parent repo

# 2. baseline + old clones
scripts/baseline/record_baseline.sh ~/purge-verify-work/baseline
scripts/baseline/make_old_clones.sh

# 3a. the ORIGINAL runbook, one step at a time (logs: ~/purge-verify-work/logs/runbook/)
for s in 0-lift 1-clone 2a-replace 2b-invert 3-verify 4-push 5-restore; do
  scripts/purge/run_runbook.sh "$s"
done

# 3b. the REVISED runbook
for p in prepare rewrite review push after; do
  scripts/purge/purge_revised.sh "$p"
done

# 4. checks
python3 scripts/verify/scan_values.py <mirror.git> --refs "refs/heads refs/tags"
scripts/verify/check_urls.sh <out.tsv> ~/purge-verify-work/baseline
scripts/baseline/record_baseline.sh <after-dir>
scripts/verify/compare_baseline.sh ~/purge-verify-work/baseline <after-dir>
python3 scripts/verify/bench_large.py --commits 10000 --gitleaks-config scripts/gitleaks/gitleaks.toml

# rollback to the backup taken by "prepare"
scripts/purge/protection.sh lift <protection-dir>
scripts/purge/rollback.sh <backup.git>
scripts/purge/protection.sh restore <protection-dir>
```

補足：

- 元の手順書の手順4は、書かれたとおりに実行すると失敗します（`origin` が消えているため）。失敗したことを記録した後、`origin` を追加し直してから続けました（レポートの項目1、表の1行目）。
- 作り直すとき、リポジトリは削除しません。ブランチとタグは force push で入れ替わります。PR と Release は追加で作られます。
