import tkinter as tk
import requests
import pytz
from datetime import datetime
import subprocess
import webbrowser
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class GitHubStatusApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub Repos Checker")

        self.user_label = tk.Label(root, text="Enter GitHub username:")
        self.user_label.pack(padx=10, pady=5)

        self.user_entry = tk.Entry(root)
        self.user_entry.pack(padx=10, pady=5)

        self.get_status_button = tk.Button(root, text="Get Repos", command=self.get_user_repos)
        self.get_status_button.pack(pady=5)

        self.repo_listbox = tk.Listbox(root)
        self.repo_listbox.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        self.last_commit_label = tk.Label(root, text="Last Commit Date:")
        self.last_commit_label.pack(padx=10, pady=5)

        self.last_commit_date = tk.Label(root, text="", fg="green")
        self.last_commit_date.pack(padx=10, pady=5)

        self.profile_link_label = tk.Label(root, text="User Profile Link:")
        self.profile_link_label.pack(padx=10, pady=5)

        self.profile_link = tk.Label(root, text="", fg="blue", cursor="hand2")
        self.profile_link.pack(padx=10, pady=5)
        self.profile_link.bind("<Button-1>", self.open_user_profile)

        self.repo_listbox.bind('<<ListboxSelect>>', self.clone_repo)

    def get_user_repos(self):
        try:
            username = self.user_entry.get()
            api_key = os.getenv('GITHUB_PAT')
            
            headers = {'Authorization': f'token {api_key}'}
            # Fetch user data
            user_response = requests.get(f'https://api.github.com/users/{username}', headers=headers)
            
            if user_response.status_code != 200:
                self.handle_error("Error fetching user data")
                return
            
            user_data = user_response.json()

            self.repo_listbox.delete(0, tk.END)
            self.last_commit_date.config(text="")
            self.profile_link.config(text="", cursor="hand2")

            repos_response = requests.get(f'https://api.github.com/users/{username}/repos', headers=headers)
            if repos_response.status_code != 200:
                self.handle_error("Error fetching user repositories")
                return

            repos_data = repos_response.json()

            last_commit = None
            for repo in repos_data:
                repo_name = repo.get('name', 'Unknown')
                self.repo_listbox.insert(tk.END, repo_name)

                commits_response = requests.get(f'https://api.github.com/repos/{username}/{repo_name}/commits', headers=headers)
                if commits_response.status_code == 200:
                    commits_data = commits_response.json()
                    if commits_data:
                        last_commit_date = commits_data[0]['commit']['author']['date']
                        last_commit_date_utc = datetime.strptime(last_commit_date, '%Y-%m-%dT%H:%M:%SZ')
                        Euro_time = pytz.timezone('Europe/Lisbon')
                        last_commit_date = last_commit_date_utc.replace(tzinfo=pytz.utc).astimezone(Euro_time)
                        
                        if not last_commit or last_commit_date > last_commit:
                            last_commit = last_commit_date

            if last_commit:
                last_commit_formatted = last_commit.strftime('%Y-%m-%d %H:%M:%S %Z')
                self.last_commit_date.config(text=f"Last Commit Date: {last_commit_formatted}", fg="green")
            else:
                self.last_commit_date.config(text="No commits found", fg="red")

            self.profile_link.config(text=f"Profile Link: {user_data['html_url']}", cursor="hand2")
        except requests.exceptions.RequestException:
            self.handle_error("Network error fetching data")

    def clone_repo(self, event):
        selected_repo = self.repo_listbox.get(self.repo_listbox.curselection())
        username = self.user_entry.get()
        repo_url = f"https://github.com/{username}/{selected_repo}.git"
        try:
            subprocess.run(["git", "clone", repo_url], check=True)
            print(f"Repository {selected_repo} cloned successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error cloning repository {selected_repo}: {str(e)}")


    def open_user_profile(self, event):
        username = self.user_entry.get()
        profile_url = f"https://github.com/{username}"
        webbrowser.open_new_tab(profile_url)
    
    def handle_error(self, message):
        self.repo_listbox.delete(0, tk.END)
        self.repo_listbox.insert(tk.END, message)
        self.last_commit_date.config(text="")
        self.profile_link.config(text="", cursor="")

if __name__ == "__main__":
    root = tk.Tk()
    app = GitHubStatusApp(root)
    root.mainloop()
