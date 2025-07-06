# GitHub Repo Checker

This project was inspired by the repository app-ideas by [@florinpop17](https://github.com/florinpop17/app-ideas).

## 🧠 Overview
Originally designed to check if GitHub was online, this project has evolved into a desktop application for analyzing and managing GitHub repositories. It uses the GitHub API and `git` to list, inspect, and clone repositories for any user.

## ✨ Features

- 🔍 **Check Last Commit Date**: Displays the most recent commit across all of a user's repositories.
- 🔗 **Profile Link**: Clickable URL to the GitHub user’s profile.
- 📦 **Clone Repositories**: Double-click any repository to clone it to a selected folder.
- 📊 **Enhanced Repo Info**: Shows stars ⭐, forks 🍴, language, and description in a sortable tree view.
- ❌ **DMCA/Unavailable Repo Detection**: Flags repositories that are inaccessible, deleted, or empty.
- 🧠 **Smart Error Detection**: Interprets Git errors (e.g., error 128) and alerts the user with a clear explanation and a link to [GitHub’s DMCA Policy](https://docs.github.com/en/github/site-policy/dmca-takedown-policy).
- 💾 **Export to CSV**: Export the entire repo list to a CSV file.
- 🌗 **Dark/Light Mode Toggle**: Using the Azure theme for a modern UI experience.
- 🔁 **Keyboard Shortcuts**:
  - `Enter` = Fetch Repos
  - `Ctrl+C` = Copy selected repo’s clone URL
- 🖱️ **Right-Click Menu**: Open the selected repository in your browser with a single click.

## 🖼️ User Interface

### Light Mode
![image](https://github.com/user-attachments/assets/bc8e4657-6457-43b5-ba45-327e1ac7d951)

### Dark Mode
![image](https://github.com/user-attachments/assets/1340160a-c919-4b9a-b9d7-d3b8d16fe8f7)

Python Tkinter Theme Created by: [@rdbende](https://github.com/rdbende/Azure-ttk-theme/tree/main)


## ⚙️ How to Set Up

1. **Create Your Personal Access Token (PAT)**:
   - [GitHub Settings Tokens](https://github.com/settings/tokens?type=beta)
   - Create a token with access to public repositories.

2. **Create a `.env` File**:
   - Store your PAT securely:
   ```env
   GITHUB_PAT=your_personal_access_token_here
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Project**:
   ```bash
   python main.py
   ```

## 📁 Project Structure 
```
GitHUB-REPO-CHECKER/
├── main.py              # Main GUI logic
├── azure.tcl            # Azure theme file
├── themes/          # Azure dark and light themes with respective icons
      ├── light.tcl            # Azure light theme file
      ├── dark.tcl             # Azure dark theme file
├── .env                 # Your GitHub PAT
├── README.md
```

## 🧩 Dependencies
- `tkinter`
- `requests`
- `pytz`
- `python-dotenv`
- `logging`
- `webbrowser`
- `subprocess`
- `csv`
- `datetime`
- `threading`
- `git` must be installed and available in PATH

---

Built with ❤️ by [Exill18](https://github.com/Exill18)

Feel free to fork and expand!
