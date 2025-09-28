# Securing your .env and removing secrets from Git history

This guide explains how to stop committing `.env`, replace the committed `.env` with a safe example file, and remove sensitive values from your Git history before pushing to GitHub.

WARNING: Rewriting Git history is destructive for shared branches. If others already cloned the repo, coordinate with them.

## Steps

1. Add `.env` to `.gitignore` (already done).

2. Create `.env.example` with placeholders (already created).

3. Replace the real `.env` in the repository with a local-only file (don't add it to git):

```powershell
# From the backend folder
mv .env .env.local
# or copy if you prefer
copy .env .env.local
Remove-Item .env
```

4. Commit the removal and add `.env.example`:

```powershell
git add .gitignore .env.example
git rm --cached .env || echo "No tracked .env"
git commit -m "Add .env to .gitignore and add .env.example; remove tracked .env"
```

5. If `.env` was accidentally committed in earlier commits, remove it from the entire history using `git filter-branch` or `git filter-repo` (recommended). Example using `git filter-repo`:

```powershell
# Install git-filter-repo if not available
pip install git-filter-repo

# From repo root (one level above backend)
# Make a backup first!
git clone --mirror . ../repo-backup.git

# Remove the file from history
git filter-repo --path backend/.env --invert-paths

# Force-push the cleaned history
git push --force origin main
```

If you cannot use `git filter-repo`, here's a `git filter-branch` alternative (slower):

```powershell
git filter-branch --force --index-filter "git rm --cached --ignore-unmatch backend/.env" --prune-empty --tag-name-filter cat -- --all
# then force push
git push origin --force --all
git push origin --force --tags
```

6. Rotate any leaked secrets immediately (GitHub tokens, API keys). Treat them as compromised.

7. Add a GitHub secret store (if deploying) instead of committing `.env`.

## Helpful tips

- Use a CI/CD secrets manager (GitHub Actions Secrets, AWS Secrets Manager, Azure Key Vault).
- Use environment variables in production, not committed files.
- Consider using a `.env.local` or OS-level secrets for local dev.

If you want, I can:
- Run the safe git commands for you here (I won't push to your remote unless you want me to).
- Create a PowerShell script `remove_env_from_history.ps1` that runs the safe commands and backs up the repo prior to rewriting history.

Which would you like me to do next?