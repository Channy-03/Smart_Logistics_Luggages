#!/usr/bin/env bash
# macOS/Linux: bash upload.sh
set -e
cd "$(dirname "$0")"
git config --global user.name >/dev/null || { read -rp "Your name for commits: " n; git config --global user.name "$n"; }
git config --global user.email >/dev/null || { read -rp "Email of your GitHub account: " e; git config --global user.email "$e"; }
echo "Commits will be made as: $(git config user.name) <$(git config user.email)>"; read -rp "Enter to continue, Ctrl+C to stop "
rm -rf work && git clone https://github.com/Channy-03/Smart_Logistics_Luggages.git work
cp -R files/. work/ && cd work
while read -r i paths; do git add $paths; git commit -q -F "../msg/$i.txt"; done < ../groups.txt
git log --format="%h %an  %s" -n 8
git checkout -q -b docs/problem-results-kyungjin && git push -u origin docs/problem-results-kyungjin
echo "Done. Create the PR: https://github.com/Channy-03/Smart_Logistics_Luggages/compare/main...docs/problem-results-kyungjin?expand=1"
