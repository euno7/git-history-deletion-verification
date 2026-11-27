# git 履歴からのシークレット削除：修正版の手順書

[English](runbook-revised.en.md)

この手順は、ダミーのリポジトリでの検証（[verification-report.ja.md](verification-report.ja.md)）で問題を直した版です。`scripts/purge/purge_revised.sh` と `scripts/purge/protection.sh` が、この手順の中心部分を実装しています。

> **前提：シークレットのローテーションが終わっていること。** 履歴を書き換えても、GitHub 上の古いコミット、fork、各自のクローン、CI のログには値が残ることがあります。履歴の削除は、ローテーションの代わりにはなりません。

## 0. 元の手順書から変えた点

| 元の手順書 | 修正版 | 理由（検証の結果） |
|---|---|---|
| `git filter-repo --replace-text ...` を実行し、続けて `--invert-paths ...` を実行（2回） | `--sensitive-data-removal --prune-empty never` を付けて、**1回**で実行 | `origin` が消えない。`first-changed-commits` が出力される。空のコミットが消えないので、コミット数が変わらない |
| `replacements.txt` に生の値だけを書く | エンコードした形（base64、URL エンコードなど）も書く。短い値は文脈つきの正規表現で書く | 消し残しと、関数名などの巻き添えを防ぐ |
| — | バイナリと圧縮ファイルは、ファイルごと削除する | `--replace-text` はバイナリを対象にしない |
| `gitleaks detect`（既定のルール） | `gitleaks git --config <独自ルール>` と、値の直接検索 | 既定のルールでは独自形式の値を検出できない |
| `git push --force --mirror origin` | `git push --force <url> 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*'`。消えたブランチは個別に削除 | `refs/pull/*` が拒否されて終了コードが 1 になる。clone の後に作られたブランチが消える |
| 「ブランチ保護を一時的に外す」 | 従来の保護と ruleset を JSON でエクスポートし、`gh api` で外して戻し、差分がないことを確かめる | 署名必須のルールも外す必要がある。戻したことを確かめる手段が要る |
| — | push の直前に、リモートの ref が変わっていないかを確かめる | 凍結が守られなかったときに、他人の push を上書きしないため |
| — | 書き換え前のバックアップと、切り戻しの手順を用意 | 失敗したときに元に戻すため（検証済み） |

## 1. 事前準備（実施日の数日前まで）

1. **ローテーション**：対象の値をすべて無効にし、新しい値に入れ替える。
2. **対象の洗い出し**：書き換え前のリポジトリで、独自ルールの gitleaks と値の直接検索を実行し、値の一覧を作る。一覧はリポジトリの外に置き、パーミッションは 600 にする。
   - 生の値だけでなく、エンコードした形（base64、URL エンコード、JSON や YAML でエスケープした形）も調べる
   - 値を含むバイナリファイルと圧縮ファイルを調べる（gitleaks はこれらの中を検出しない）
   - `password` のような短い値は、出てくる場所をすべて調べる
3. **スキャナーのルールの確認**：独自のルールが、書き換え前の全件を検出できることを確かめる（**0 件なら、ルールが合っていない**）。
4. **置換リストとパスの一覧を作る**（リポジトリの外に置く）。

   ```text
   <値>==>REMOVED_SECRET
   <値の base64>==>REMOVED_SECRET
   <値の URL エンコード>==>REMOVED_SECRET
   regex:(ADMIN_PASSWORD\s*=\s*)"<短い値>"==>\1"REMOVED_SECRET"
   ```

   ファイルごと消すもの：`.env`、鍵ファイル、値を含むバイナリと圧縮ファイル。

5. **予行演習**：ミラーのコピーで、手順3〜4（書き換えと確認）を実行し、所要時間を測る。push はしない。
6. **オープン中の PR の整理**：できるだけマージするかクローズする（GitHub が勧めている。古い差分へのコメントが失われるため）。
7. **影響範囲の確認**
   - fork の一覧：`gh api repos/<owner>/<repo>/forks --paginate`
   - このリポジトリを submodule として参照しているリポジトリ
   - SHA を記録している仕組み（デプロイ記録、リリースノート、課題管理）
8. **告知**：開発者に、凍結の日時と事後の作業を伝える（[developer-notice.ja.md](developer-notice.ja.md)）。
9. **値をログに出すワークフローを無効にする**：push のたびに Actions のログに値がまた出るため（`gh workflow disable <name>`）。

## 2. 実行（凍結の開始）

凍結の枠は、小さなリポジトリでも 30〜60 分を目安にします（機械の作業は1分程度ですが、人による確認の時間が必要です）。

```bash
# 2-1. protection settings + remote ref snapshot + backup mirror
scripts/purge/purge_revised.sh prepare
#   = protection.sh export <dir>            (classic protection and rulesets as JSON)
#   = git ls-remote <url> > remote_refs_before.txt
#   = git clone --mirror <url> backup.git && tar czf backup-mirror.tgz backup.git

# 2-2. rewrite (one filter-repo run)
scripts/purge/purge_revised.sh rewrite
#   = git clone --mirror <url> mirror.git
#     cd mirror.git
#     git filter-repo --sensitive-data-removal --prune-empty never \
#       --replace-text ../replacements.txt \
#       --invert-paths --path .env --path <key file> --path <binary> ...
#   (delete replacements.txt afterwards)
```

`--sensitive-data-removal` には git filter-repo 2.47 以上が必要です。出力の「First Changed Commit(s)」を記録してください。

## 3. 確認（push の前）

```bash
scripts/purge/purge_revised.sh review
```

次のすべてを満たすまで、push しません。

- [ ] 独自ルールの gitleaks（`--log-opts="--branches --tags"`）が 0 件
- [ ] 値の直接検索（`scripts/verify/scan_values.py`：生の値、base64、URL エンコード、gzip の中身）で、ブランチとタグからたどれる値が 0 件
- [ ] ブランチとタグごとに、変わったファイルが想定したものだけ
- [ ] 主要なブランチの先端で、**追加された行**を目で確かめ、関係ないコードが変わっていない（削除された行は値を含むので画面に出さない）
- [ ] 書き換え後の先端でテストが通る
- [ ] 書き換え前と比べて、ブランチごとのコミット数、件名、`version..develop` の件数と件名、merge-base、マージの構造が一致する（`scripts/baseline/record_baseline.sh` と `scripts/verify/compare_baseline.sh`）

## 4. push

```bash
scripts/purge/purge_revised.sh push
#   1. abort if branches/tags on the remote changed since "prepare"
#   2. protection.sh lift      (DELETE classic protection, rulesets -> disabled)
#   3. git push --force <url> 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*'
#   4. delete refs that filter-repo removed (ref-map rows whose new SHA is all zeros)
#   5. protection.sh restore   (PUT classic protection + required_signatures, rulesets -> active)
#   6. protection.sh compare   (must print SAME for every item)
```

- `--mirror` は使いません。`refs/pull/*` は GitHub が更新を受け付けません（「hidden ref」として拒否）。また、`--mirror` は clone の後にリモートに作られたブランチを削除してしまいます。
- 手順1で中止した場合は、凍結が守られていません。手順 2-2 からやり直します。

## 5. 事後の確認と対応

```bash
scripts/purge/purge_revised.sh after
#   fresh mirror clone from GitHub -> gitleaks + direct search on branches/tags
#   lists what still remains under refs/pull/*
#   prints the data for a GitHub Support request
```

1. **保護を戻したこと**：`protection.sh compare` がすべて SAME であること。
2. **値をログに出すワークフロー**：無効のままにするか、直してから有効にする。
3. **PR の本文とコメント**：値を書いた本文を編集し、コメントを削除する。**編集履歴に元の文章が残る**ので、Web 画面の「edited」から、その版を履歴から削除する。
4. **Actions のログ**：値が出た実行を `gh run delete <id>` で削除する。
5. **Release の添付ファイル**：値を含む添付ファイルを削除し、作り直して添付する。
6. **submodule の参照**：参照しているリポジトリで、`commit-map` を使って新しい SHA に付け替える。
7. **SHA の記録**：`commit-map`、`ref-map`、`first-changed-commits` を社内の安全な場所に保存する（値は含まないが、古いコミットを探す手がかりになる）。
8. **開発者の再クローン**：全員から完了の報告を受け取る（[developer-notice.ja.md](developer-notice.ja.md)）。
9. **新しいブランチ作成の制限**：全員の再クローンが終わるまで、ruleset で `refs/heads/**` の作成と force push を制限することを検討する。古いクローンからの push で値が戻ることを防ぐため。
10. **GitHub サポートへの依頼**（必要な場合）
    - GitHub は、ローテーションでリスクを抑えられない場合にだけ対応する
    - 依頼に含めるもの：リポジトリ名、影響を受ける PR の数（`grep -c '^refs/pull/.*/head$' .git/filter-repo/changed-refs`）、First Changed Commit(s)
    - サポートの作業：キャッシュされた表示の削除、PR の参照の削除または切り離し、サーバー側の GC
    - fork はサポートでも消せない
11. **fork**：fork の所有者に、削除または同じ書き換えを依頼する。

## 6. 切り戻し

push の後に問題が見つかった場合は、事前のバックアップに戻します（検証済み：元の SHA に完全に戻り、署名も元どおりになった）。

```bash
scripts/purge/protection.sh lift <protection-dir>
scripts/purge/rollback.sh <backup.git>   # git push --force <url> 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*'
scripts/purge/protection.sh restore <protection-dir>
scripts/purge/protection.sh compare <protection-dir>
```

注意：

- 切り戻すと、**値も元に戻ります**（公開されている状態に戻ります）。
- 書き換えの後に作られたブランチやコミットは、バックアップに含まれません。
- `main` への push で、値をログに出すワークフローがまた動くことがあります。事前に無効にしておいてください。

## 7. 「履歴削除が完了した」と言える条件

次のすべてを満たしたときに、完了とします。

1. 対象の値がすべてローテーション済みで、古い値が使えないことを確認した
2. GitHub から新しくクローンしたミラーで、ブランチとタグに対して、独自ルールの gitleaks と値の直接検索の結果がどちらも 0 件
3. ブランチ保護と ruleset が、事前のエクスポートと一致している
4. PR の本文、コメント、その編集履歴、Actions のログ、Release の添付ファイルに値が残っていない
5. 開発者全員が再クローンを終え、古いクローンを削除した
6. submodule や SHA の記録の付け替えが終わった
7. GitHub サポートへの依頼が必要な場合は、その対応（`refs/pull/*` の古い参照と、古いコミットの URL の削除）が終わり、古いコミットの URL にアクセスできないことを確かめた。依頼しない場合は、その判断と理由（ローテーション済みであることなど）を記録した
8. fork があれば、その対応が終わった
