# GitHub Repo Checker

This project was inspired by the repository app-ideas by [@florinpop17](https://github.com/florinpop17/app-ideas).

## 🧠 Overview
Originally designed to check if GitHub was online, this project has evolved into a responsive desktop application for analyzing and managing GitHub repositories. It uses the GitHub API and `GitPython` to list, inspect, and clone repositories for any user, with a focus on handling large accounts efficiently.

## ✨ Features

- 🚀 **Progressive Loading**: Repositories are streamed in page by page, making the application instantly responsive even for users with thousands of repositories.
- 👤 **User Avatar**: Fetches and displays the GitHub user's profile picture.
- 🔎 **Real-time Search**: Instantly filter the repository list as you type.
- 📊 **Enhanced Repo Info**: Shows name, stars ⭐, forks 🍴, language, and description in a sortable tree view.
- 🔗 **Profile Link**: Clickable URL to the GitHub user’s profile.
- 📦 **Clone with GitPython**: Double-click any repository to clone it to a selected folder using the `GitPython` library.
- 💾 **Export to CSV**: Export the entire filtered list of repositories to a CSV file.
- 🌗 **Dark/Light Mode Toggle**: Uses the Azure-ttk-theme for a modern UI experience.
- 🔁 **Keyboard Shortcuts**:
  - `Enter` = Fetch Repos
  - `Ctrl+C` = Copy selected repo’s clone URL
- 🖱️ **Right-Click Menu**: Quickly open a repository in your browser, copy its clone URL, or initiate a clone.
- 📈 **Rate Limit Handling**: Checks GitHub API rate limits, informing the remaining requests and when the limit will reset.

## 🖼️ User Interface

### Light Mode
![image](https://github.com/user-attachments/assets/fcb99ddf-507f-4151-881f-9a71b31b190b)

### Dark Mode
![image](https://github.com/user-attachments/assets/8f1c85dd-14ca-4c73-8226-20c5f8509037)

Python Tkinter Theme Created by: [@rdbende](https://github.com/rdbende/Azure-ttk-theme/tree/main)


## ⚙️ How to Set Up

1.  **Create Your Personal Access Token (PAT)**:
    - Go to [GitHub Settings Tokens](https://github.com/settings/tokens?type=beta).
    - Create a token with `public_repo` access. This provides a much higher API rate limit.

2.  **Create a `.env` File**:
    - In the project's root directory, create a file named `.env`.
    - Store your PAT securely in this file:
      ```env
      GITHUB_PAT=your_personal_access_token_here
      ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the Project**:
    ```bash
    python main.py
    ```

## 📁 Project Structure 
```
GitHUB-REPO-CHECKER/
├── main.py              # Main application logic and UI
├── github_api.py        # Handles all communication with the GitHub API
├── azure.tcl            # Azure theme file
├── themes/              # Azure dark and light theme assets
│   ├── light.tcl
│   └── dark.tcl
├── .env                 # Stores your GitHub PAT (must be created by you)
├── requirements.txt     # Lists all project dependencies
└── README.md
```

## 🧩 Dependencies
The project's dependencies are listed in the `requirements.txt` file.

- `requests` for making HTTP requests to the GitHub API.
- `python-dotenv` for managing environment variables (like your PAT).
- `pytz` for handling timezones for commit dates.
- `Pillow` for processing and displaying the user avatar.
- `GitPython` for a robust, object-oriented interface to your local Git repositories.
- `git` command-line tool must be installed and available in your system's PATH.

---

Developed by [Exill18](https://github.com/Exill18)

Feel free to fork and expand!
