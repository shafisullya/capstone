#!/bin/bash

# Simple script to push generated files to GitHub
echo "🚀 Starting GitHub push..."

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Add all files to staging area
echo "📁 Adding files to git staging area..."
git add .
git add index.html  # Explicitly add index.html in case it's ignored

# Check if there are changes to commit
if git diff --staged --quiet; then
    echo "ℹ️ No changes to commit"
    exit 0
fi

# Show what will be committed
echo "📋 Files to be committed:"
git status --staged --short

# Get current branch name
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "🌿 Current branch: $BRANCH"

# Commit with timestamp
commit_msg="Auto-generated files - $(date '+%Y-%m-%d %H:%M:%S')"
echo "💾 Committing with message: '$commit_msg'"
git commit -m "$commit_msg"

# Check if remote origin exists
if ! git remote get-url origin > /dev/null 2>&1; then
    echo "❌ Error: No remote 'origin' configured"
    echo "ℹ️ Please add a remote origin: git remote add origin <your-repo-url>"
    exit 1
fi

# Push to remote origin
echo "🚀 Pushing to origin/$BRANCH..."
if git push origin "$BRANCH"; then
    echo "✅ Successfully pushed to GitHub!"
    echo "📊 Latest commit:"
    git log --oneline -1
else
    echo "❌ Failed to push to GitHub"
    echo "ℹ️ Check your network connection and GitHub credentials"
    exit 1
fi