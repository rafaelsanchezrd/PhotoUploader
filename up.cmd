@echo off
set /p commitMessage="Enter your commit message: "
git add .
git commit -m "%commitMessage%"
git push