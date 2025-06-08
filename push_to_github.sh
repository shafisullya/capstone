#!/bin/bash


set -e
source .env

git config user.email "$GIT_USER_EMAIL"
git config user.name "$GITHUB_USERNAME"

git remote set-url origin "https://$GITHUB_USERNAME:$GITHUB_PAT@github.com/${GITHUB_USERNAME}/capstone.git"

git add index.html
git commit -m "Update index.html with latest code from multi-agent chat"
git push origin main

FILE="index.html"
COMMIT_MSG="Update index.html with latest code from multi-agent chat"


if [[ ! -f "$FILE" ]]; then
  echo "File '$FILE' does not exist. Nothing to commit."
  exit 1
fi


echo "Staging $FILE..."
git add "$FILE"


echo "Committing with message: $COMMIT_MSG"
git commit -m "$COMMIT_MSG"


echo "Pushing to GitHub..."
git push origin main

echo "Push complete!"
