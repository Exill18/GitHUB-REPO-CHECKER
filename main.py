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
import shutil
from datetime import datetime
from dotenv import load_dotenv, set_key

# --- Setup ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
CONFIG_FILE = ".env"

class GitHubRepoChecker:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub Repos Checker")
        self.root.geometry("900x600")

        self.repo_commit_cache = {}
        self.repo_flags = {}
        self.profile_link_url = ""

        self.progress = tk.DoubleVar()

        self.current_theme = os.getenv("UI_THEME", "light")
        try:
            self.root.tk.call("source", "azure.tcl")
            self.root.tk.call("set_theme", self.current_theme)
        except tk.TclError as e:
            print(f"Failed to load Azure theme: {e}")
            self.current_theme = None

        self.page_size = 25
        self.current_page = 0
        self.filtered_repos = []

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

        self.progress_bar = ttk.Progressbar(self.root, mode="indeterminate", variable=self.progress)
        self.progress_bar.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.progress_bar.pack_forget()

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

        self.sort_state = {"column": None, "descending": False}
        for col in columns:
            self.tree.heading(col, text=self.tree.heading(col)["text"],
                              command=lambda _col=col: self.sort_treeview_column(_col))

        self.tree.bind("<Double-1>", lambda e: self.threaded_clone_repo())
        self.tree.bind("<Button-3>", self.open_selected_repo_web)

        nav_frame = ttk.Frame(self.root)
        nav_frame.pack(pady=5)
        ttk.Button(nav_frame, text="◀ Previous", command=self.prev_page).pack(side=tk.LEFT, padx=5)
        ttk.Button(nav_frame, text="Next ▶", command=self.next_page).pack(side=tk.LEFT, padx=5)

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
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        try:
            self.root.tk.call("set_theme", self.current_theme)
            set_key(CONFIG_FILE, "UI_THEME", self.current_theme)
        except tk.TclError:
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
        self.progress_bar.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.progress_bar.start()

        try:
            user_resp = requests.get(f"https://api.github.com/users/{username}", headers=headers)
            if user_resp.status_code == 403:
                reset_time_unix = user_resp.headers.get("X-RateLimit-Reset")
                rate_remaining = user_resp.headers.get("X-RateLimit-Remaining")
                rate_limit = user_resp.headers.get("X-RateLimit-Limit")
                if reset_time_unix:
                    reset_dt = datetime.fromtimestamp(int(reset_time_unix)).astimezone()
                    reset_str = reset_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
                else:
                    reset_str = "unknown"
                message = (f"GitHub API rate limit reached.\n"
                           f"Limit: {rate_limit}, Remaining: {rate_remaining}\n"
                           f"Resets at: {reset_str}")
                self.update_status(message)
                messagebox.showwarning("Rate Limit", message)
                return
            elif user_resp.status_code != 200:
                logging.error(f"User fetch failed: {user_resp.status_code}, {user_resp.text}")
                self.update_status("User not found or error fetching profile.")
                return

            user_data = user_resp.json()
            self.profile_link.config(text=f"Profile: {user_data['html_url']}")
            self.profile_link_url = user_data['html_url']

            self.repo_commit_cache.clear()
            self.repo_flags.clear()
            last_commit = None

            all_repos = []
            page = 1
            while True:
                repo_resp = requests.get(
                    f"https://api.github.com/users/{username}/repos?per_page=100&page={page}&sort=updated",
                    headers=headers
                )
                if repo_resp.status_code == 403:
                    self.update_status("Rate limit reached while fetching repos.")
                    return
                if repo_resp.status_code != 200:
                    logging.error(f"Repo fetch failed: {repo_resp.status_code}, {repo_resp.text}")
                    break
                page_data = repo_resp.json()
                if not page_data:
                    break
                all_repos.extend(page_data)
                page += 1

            self.filtered_repos = all_repos
            self.current_page = 0
            self.display_repos_page()

            for repo in all_repos:
                if 'pushed_at' in repo:
                    pushed = datetime.strptime(repo['pushed_at'], '%Y-%m-%dT%H:%M:%SZ')
                    lisbon_time = pytz.timezone("Europe/Lisbon")
                    pushed_local = pushed.replace(tzinfo=pytz.utc).astimezone(lisbon_time)
                    self.repo_commit_cache[repo['name']] = pushed_local
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
        finally:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()

    def display_repos_page(self):
        start = self.current_page * self.page_size
        end = start + self.page_size
        current_repos = self.filtered_repos[start:end]

        self.tree.delete(*self.tree.get_children())
        self.repo_flags.clear()

        for repo in current_repos:
            name = repo["name"]
            stars = repo.get("stargazers_count", 0)
            forks = repo.get("forks_count", 0)
            lang = repo.get("language", "") or "-"
            desc = repo.get("description", "") or "-"
            flagged_name = name
            self.tree.insert("", "end", iid=flagged_name, values=(stars, forks, lang, desc))

        total_pages = ((len(self.filtered_repos) - 1) // self.page_size) + 1
        self.update_status(f"Page {self.current_page + 1} of {total_pages}")

    def next_page(self):
        if (self.current_page + 1) * self.page_size < len(self.filtered_repos):
            self.current_page += 1
            self.display_repos_page()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_repos_page()

    def sort_treeview_column(self, col):
        items = list(self.tree.get_children())
        if not items:
            return

        descending = self.sort_state.get("column") == col and not self.sort_state["descending"]
        self.sort_state = {"column": col, "descending": descending}

        def sort_key(iid):
            val = self.tree.set(iid, col)
            try:
                return int(val)
            except ValueError:
                return val.lower()

        sorted_items = sorted(items, key=sort_key, reverse=descending)

        for idx, item in enumerate(sorted_items):
            self.tree.move(item, '', idx)

    def update_status(self, message):
        self.status_label.config(text=message)

    def open_user_profile(self, event):
        if self.profile_link_url:
            webbrowser.open_new_tab(self.profile_link_url)

    def open_selected_repo_web(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        repo_name = selected[0]
        username = self.user_entry.get().strip()
        url = f"https://github.com/{username}/{repo_name}"
        webbrowser.open_new_tab(url)

    def copy_repo_url_to_clipboard(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        repo_name = selected[0]
        username = self.user_entry.get().strip()
        url = f"https://github.com/{username}/{repo_name}.git"
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self.update_status(f"Copied to clipboard: {url}")

    def threaded_clone_repo(self):
        threading.Thread(target=self.clone_repo, daemon=True).start()

    def clone_repo(self):
        selected = self.tree.selection()
        if not selected:
            return
        repo_name = selected[0]
        username = self.user_entry.get().strip()
        repo_url = f"https://github.com/{username}/{repo_name}.git"

        if shutil.which("git") is None:
            messagebox.showerror("Git Not Found", "Git is not installed or not in PATH.")
            return

        folder = filedialog.askdirectory(title="Choose folder to clone into")
        if not folder:
            return

        self.progress_bar.start()
        clone_path = os.path.join(folder, repo_name)
        try:
            subprocess.run(["git", "clone", repo_url, clone_path], check=True)
            messagebox.showinfo("Success", f"Repository '{repo_name}' cloned to {folder}")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.lower()
            if "repository not found" in stderr or "could not read from remote" in stderr:
                msg = (f"The repository '{repo_name}' appears to be removed, DMCA'd, or unavailable.\n\n"
                       "Learn more: https://docs.github.com/en/github/site-policy/dmca-takedown-policy")
                messagebox.showerror("Clone Failed", msg)
            else:
                messagebox.showerror("Clone Failed", f"An error occurred while cloning:\n\n{stderr}")
        finally:
            self.progress_bar.stop()

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
                        writer.writerow([name, stars, forks, lang, desc])
                self.update_status(f"Exported to {path}")
            except Exception as e:
                logging.error("Export failed", exc_info=True)
                messagebox.showerror("Export Failed", f"Failed to export CSV:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = GitHubRepoChecker(root)
    root.mainloop()
