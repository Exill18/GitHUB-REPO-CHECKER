import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import requests
import threading
import logging
import os
import webbrowser
import subprocess
import pytz
import csv
from datetime import datetime
from dotenv import load_dotenv

# --- Setup ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

class GitHubStatusApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub Repos Checker")
        self.root.geometry("900x600")

        self.repo_commit_cache = {}
        self.repo_flags = {}

        try:
            self.root.tk.call("source", "azure.tcl")
            self.root.tk.call("set_theme", "light")
            self.current_theme = "light"
        except tk.TclError as e:
            print(f"Failed to load Azure theme: {e}")
            self.current_theme = None

        self.create_widgets()
        self.bind_shortcuts()

    def create_widgets(self):
        top_frame = ttk.Frame(self.root)
        top_frame.pack(pady=10, fill=tk.X)

        ttk.Label(top_frame, text="GitHub Username:").pack(side=tk.LEFT, padx=(10, 5))
        self.user_entry = ttk.Entry(top_frame)
        self.user_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.get_status_button = ttk.Button(top_frame, text="Get Repos", command=self.threaded_get_user_repos)
        self.get_status_button.pack(side=tk.LEFT, padx=5)

        self.export_button = ttk.Button(top_frame, text="Export CSV", command=self.export_to_csv)
        self.export_button.pack(side=tk.LEFT, padx=5)

        columns = ("stars", "forks", "lang", "desc")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("stars", text="⭐ Stars")
        self.tree.heading("forks", text="🍴 Forks")
        self.tree.heading("lang", text="Language")
        self.tree.heading("desc", text="Description")
        self.tree.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        self.tree.column("stars", width=60, anchor="center")
        self.tree.column("forks", width=60, anchor="center")
        self.tree.column("lang", width=100, anchor="center")
        self.tree.column("desc", anchor="w")

        self.tree.bind("<Double-1>", self.clone_repo)
        self.tree.bind("<Button-3>", self.open_selected_repo_web)

        self.last_commit_label = ttk.Label(self.root, text="Last Commit: -")
        self.last_commit_label.pack(pady=(5, 0))

        self.profile_link = ttk.Label(self.root, text="", foreground="blue", cursor="hand2")
        self.profile_link.pack()
        self.profile_link.bind("<Button-1>", self.open_user_profile)

        self.status_label = ttk.Label(self.root, text="", foreground="gray")
        self.status_label.pack(pady=5)

        self.theme_toggle_button = ttk.Button(self.root, text="Toggle Theme", command=self.toggle_theme)
        self.theme_toggle_button.pack(pady=10)

    def bind_shortcuts(self):
        self.root.bind('<Return>', lambda e: self.threaded_get_user_repos())
        self.root.bind('<Control-c>', self.copy_repo_url_to_clipboard)

    def toggle_theme(self):
        if self.current_theme == "light":
            self.root.tk.call("set_theme", "dark")
            self.current_theme = "dark"
        elif self.current_theme == "dark":
            self.root.tk.call("set_theme", "light")
            self.current_theme = "light"
        else:
            messagebox.showerror("Theme Error", "Azure theme is not loaded.")

    def threaded_get_user_repos(self):
        threading.Thread(target=self.get_user_repos, daemon=True).start()

    def get_user_repos(self):
        username = self.user_entry.get().strip()
        if not username:
            messagebox.showwarning("Input Required", "Please enter a GitHub username.")
            return

        token = os.getenv("GITHUB_PAT")
        headers = {"Authorization": f"token {token}"} if token else {}

        self.update_status("Fetching user data...")
        try:
            user_resp = requests.get(f"https://api.github.com/users/{username}", headers=headers)
            if user_resp.status_code != 200:
                self.update_status("User not found or error fetching profile.")
                return

            user_data = user_resp.json()
            self.profile_link.config(text=f"Profile: {user_data['html_url']}")
            self.profile_link_url = user_data['html_url']

            self.tree.delete(*self.tree.get_children())
            self.repo_commit_cache.clear()
            self.repo_flags.clear()
            last_commit = None

            all_repos = []
            for page in range(1, 4):
                repo_resp = requests.get(
                    f"https://api.github.com/users/{username}/repos?per_page=100&page={page}&sort=updated",
                    headers=headers
                )
                if repo_resp.status_code != 200:
                    break
                page_data = repo_resp.json()
                if not page_data:
                    break
                all_repos.extend(page_data)

            for repo in all_repos:
                name = repo["name"]
                stars = repo.get("stargazers_count", 0)
                forks = repo.get("forks_count", 0)
                lang = repo.get("language", "") or "-"
                desc = repo.get("description", "") or "-"

                # Check if repo can be cloned
                clone_url = f"https://github.com/{username}/{name}.git"
                try:
                    result = subprocess.run(["git", "ls-remote", clone_url], capture_output=True, text=True)
                    if result.returncode != 0 or not result.stdout.strip():
                        flagged_name = f"❌ {name}"
                        self.repo_flags[flagged_name] = name
                    else:
                        flagged_name = name
                except Exception:
                    flagged_name = f"❌ {name}"
                    self.repo_flags[flagged_name] = name

                self.tree.insert("", "end", iid=flagged_name, values=(stars, forks, lang, desc))

                if 'pushed_at' in repo:
                    pushed = datetime.strptime(repo['pushed_at'], '%Y-%m-%dT%H:%M:%SZ')
                    lisbon_time = pytz.timezone("Europe/Lisbon")
                    pushed_local = pushed.replace(tzinfo=pytz.utc).astimezone(lisbon_time)
                    self.repo_commit_cache[flagged_name] = pushed_local
                    if not last_commit or pushed_local > last_commit:
                        last_commit = pushed_local

            if last_commit:
                self.last_commit_label.config(text=f"Last Commit: {last_commit.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            else:
                self.last_commit_label.config(text="Last Commit: None found")

            self.update_status(f"Loaded {len(all_repos)} repositories.")
        except Exception as e:
            logging.error("Error fetching repos", exc_info=True)
            self.update_status("Network or API error occurred.")

    def update_status(self, message):
        self.status_label.config(text=message)

    def open_user_profile(self, event):
        if hasattr(self, 'profile_link_url'):
            webbrowser.open_new_tab(self.profile_link_url)

    def open_selected_repo_web(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        repo_name = selected[0]
        if repo_name in self.repo_flags:
            repo_name = self.repo_flags[repo_name]
        username = self.user_entry.get().strip()
        url = f"https://github.com/{username}/{repo_name}"
        webbrowser.open_new_tab(url)

    def copy_repo_url_to_clipboard(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        repo_name = selected[0]
        if repo_name in self.repo_flags:
            repo_name = self.repo_flags[repo_name]
        username = self.user_entry.get().strip()
        url = f"https://github.com/{username}/{repo_name}.git"
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self.update_status(f"Copied to clipboard: {url}")

    def clone_repo(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        repo_name = selected[0]
        original_name = self.repo_flags.get(repo_name, repo_name)
        username = self.user_entry.get().strip()
        repo_url = f"https://github.com/{username}/{original_name}.git"

        folder = filedialog.askdirectory(title="Choose folder to clone into")
        if not folder:
            return

        clone_path = os.path.join(folder, original_name)
        try:
            result = subprocess.run(
                ["git", "clone", repo_url, clone_path],
                capture_output=True,
                text=True,
                check=True
            )
            messagebox.showinfo("Success", f"Repository '{original_name}' cloned to {folder}")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.lower()
            if "repository not found" in stderr or "could not read from remote repository" in stderr or "does not appear to be a git repository" in stderr:
                msg = (
                    f"The repository '{original_name}' appears to be removed, DMCA'd, or otherwise unavailable for cloning.\n\n"
                    "Learn more: https://docs.github.com/en/github/site-policy/dmca-takedown-policy"
                )
                messagebox.showerror("Clone Failed", msg)
            elif e.returncode == 128:
                messagebox.showerror("Clone Failed", f"Git error 128: Repository might be inaccessible or empty.\n\nDetails:\n{stderr}")
            else:
                messagebox.showerror("Clone Failed", f"An error occurred while cloning:\n\n{stderr}")
            logging.error("Git clone failed", exc_info=True)

    def export_to_csv(self):
        if not self.tree.get_children():
            messagebox.showwarning("No Data", "No repositories to export.")
            return

        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if path:
            try:
                with open(path, "w", newline='', encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Name", "Stars", "Forks", "Language", "Description"])
                    for row in self.tree.get_children():
                        name = row
                        stars, forks, lang, desc = self.tree.item(row)["values"]
                        original_name = self.repo_flags.get(name, name)
                        writer.writerow([original_name, stars, forks, lang, desc])
                self.update_status(f"Exported to {path}")
            except Exception as e:
                logging.error("Export failed", exc_info=True)
                messagebox.showerror("Export Failed", f"Failed to export CSV:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = GitHubStatusApp(root)
    root.mainloop()