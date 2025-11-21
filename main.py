
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import logging
import os
import webbrowser
import pytz
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv, set_key
from PIL import Image, ImageTk
import io
import urllib.request
import urllib.error
import git
from queue import Queue, Empty
from itertools import count, cycle
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional, Tuple

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from github_api import GitHubAPI

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('github_repo_checker.log')
    ]
)
logger = logging.getLogger(__name__)

CONFIG_FILE = ".env"

class SplashScreen:
    def __init__(self, parent: tk.Tk) -> None:
        self.root = parent
        self.window = tk.Toplevel(parent)
        self.window.overrideredirect(True)
        self.is_running = True
        
        try:
            self.gif_path = "loading.gif"
            self.gif_info = Image.open(self.gif_path)
            self.frames = self.get_frames(self.gif_info)
            self.frame_iterator = cycle(self.frames)
            logger.info("Splash screen initialized successfully")
        except FileNotFoundError:
            logger.warning("loading.gif not found. Skipping splash screen animation.")
            self.frames = None
            self.close()
            return
        except Exception as e:
            logger.error(f"Failed to initialize splash screen: {e}")
            self.frames = None
            self.close()
            return
        width, height = self.gif_info.size
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')
        self.label = ttk.Label(self.window)
        self.label.pack()
        self.animate()

    def get_frames(self, image: Image.Image) -> List[ImageTk.PhotoImage]:
        """Extract frames from animated GIF."""
        frame_list = []
        try:
            for i in count(1):
                try:
                    image.seek(i)
                    frame_list.append(ImageTk.PhotoImage(image.copy()))
                except EOFError:
                    break
            logger.debug(f"Extracted {len(frame_list)} frames from GIF")
        except Exception as e:
            logger.error(f"Error extracting frames: {e}")
        return frame_list

    def animate(self) -> None:
        """Animate the splash screen GIF."""
        if not self.is_running or not self.frames:
            return
        try:
            current_frame = next(self.frame_iterator)
            self.label.configure(image=current_frame)
            self.root.after(self.gif_info.info.get('duration', 100), self.animate)
        except Exception as e:
            logger.error(f"Error during animation: {e}")

    def close(self) -> None:
        """Close the splash screen."""
        self.is_running = False
        try:
            self.window.destroy()
            logger.debug("Splash screen closed")
        except Exception as e:
            logger.error(f"Error closing splash screen: {e}")

class GitHubRepoChecker:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("GitHub Repo Checker")
        self.root.geometry("1100x800")
        
        # Initialize core components
        self.api = GitHubAPI()
        self.repo_queue: Queue = Queue()
        
        # Data storage
        self.all_repos: List[Dict[str, Any]] = []
        self.filtered_repos: List[Dict[str, Any]] = []
        
        # UI state
        self.profile_link_url = ""
        self.sort_state: Dict[str, Any] = {}
        
        # Theme management
        self.current_theme = os.getenv("UI_THEME", "light")
        self._setup_theme()
        
        # Pagination
        self.page_size = 25
        self.current_page = 0
        
        # Insights
        self.insight_canvases: List[Any] = []
        
        # UI attributes that will be set during widget creation
        self.avatar_image: Optional[ImageTk.PhotoImage] = None
        
        logger.info("Initializing GitHub Repo Checker application")
        
        try:
            self.create_widgets()
            self.bind_shortcuts()
            self.process_repo_queue()
            logger.info("Application initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            raise
            
    def _setup_theme(self) -> None:
        """Set up the application theme."""
        try:
            self.root.tk.call("source", "azure.tcl")
            self.root.tk.call("set_theme", self.current_theme)
            logger.info(f"Applied {self.current_theme} theme")
        except tk.TclError as e:
            logger.warning(f"Azure theme not found: {e}. Using default theme.")
            self.current_theme = None
        except Exception as e:
            logger.error(f"Error setting up theme: {e}")
            self.current_theme = None
    
    def _validate_username(self, username: str) -> Tuple[bool, str]:
        """Validate GitHub username input.
        
        Returns:
            Tuple of (is_valid: bool, error_message: str)
        """
        if not username or not isinstance(username, str):
            return False, "Username must be a non-empty string"
            
        username = username.strip()
        if not username:
            return False, "Username cannot be empty"
            
        if len(username) > 39:  # GitHub username max length
            return False, "Username cannot be longer than 39 characters"
            
        if not all(c.isalnum() or c in '-._' for c in username):
            return False, "Username contains invalid characters"
            
        if username.startswith('-') or username.endswith('-'):
            return False, "Username cannot start or end with a hyphen"
            
        return True, ""
    
    def _validate_file_path(self, file_path: str) -> Tuple[bool, str]:
        """Validate file path for safety.
        
        Returns:
            Tuple of (is_valid: bool, error_message: str)
        """
        if not file_path or not isinstance(file_path, str):
            return False, "File path must be a non-empty string"
            
        try:
            # Check if path is accessible and safe
            if not os.path.exists(file_path):
                return False, "Path does not exist"
                
            if not os.path.isdir(file_path):
                return False, "Path is not a directory"
                
            if not os.access(file_path, os.W_OK):
                return False, "No write permission for this directory"
                
            return True, ""
        except Exception as e:
            logger.error(f"Error validating file path {file_path}: {e}")
            return False, f"Invalid path: {e}"

    def create_widgets(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.repos_tab = ttk.Frame(self.notebook)
        self.insights_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.repos_tab, text="Repos")
        self.notebook.add(self.insights_tab, text="Insights")
        self.notebook.pack(fill=tk.BOTH, expand=True)

        top_frame = ttk.Frame(self.repos_tab)
        top_frame.pack(pady=10, padx=10, fill=tk.X)

        self.avatar_label = ttk.Label(top_frame)
        self.avatar_label.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(top_frame, text="GitHub Username or Org:").pack(side=tk.LEFT)
        self.user_entry = ttk.Entry(top_frame)
        self.user_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.user_entry.focus()

        self.get_repos_button = ttk.Button(top_frame, text="Get Repos", command=self.start_repo_fetch)
        self.get_repos_button.pack(side=tk.LEFT)

        tool_frame = ttk.Frame(self.repos_tab)
        tool_frame.pack(pady=5, padx=10, fill=tk.X)

        ttk.Label(tool_frame, text="Search:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(tool_frame)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.search_entry.bind("<KeyRelease>", self.filter_repos)

        self.export_button = ttk.Button(tool_frame, text="Export CSV", command=self.export_to_csv)
        self.export_button.pack(side=tk.LEFT, padx=5)

        self.theme_toggle_button = ttk.Button(tool_frame, text="Toggle Theme", command=self.toggle_theme)
        self.theme_toggle_button.pack(side=tk.LEFT)

        self.progress_bar = ttk.Progressbar(self.repos_tab, mode="indeterminate")
        self.progress_bar.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.progress_bar.pack_forget()

        columns = ("name", "stars", "forks", "lang", "desc")
        self.tree = ttk.Treeview(self.repos_tab, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("name", text="Repository Name", command=lambda: self.sort_by_column("name"))
        self.tree.column("name", width=250, stretch=False)
        self.tree.heading("stars", text="⭐ Stars", command=lambda: self.sort_by_column("stargazers_count"))
        self.tree.column("stars", width=80, anchor="center", stretch=False)
        self.tree.heading("forks", text="🍴 Forks", command=lambda: self.sort_by_column("forks_count"))
        self.tree.column("forks", width=80, anchor="center", stretch=False)
        self.tree.heading("lang", text="Language", command=lambda: self.sort_by_column("language"))
        self.tree.column("lang", width=140, anchor="w", stretch=False)
        self.tree.heading("desc", text="Description")
        self.tree.column("desc", width=500)
        self.tree.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.threaded_clone_repo)
        self.tree.bind("<Button-3>", self.show_context_menu)

        nav_frame = ttk.Frame(self.repos_tab)
        nav_frame.pack(pady=5)
        ttk.Button(nav_frame, text="◀ Previous", command=self.prev_page).pack(side=tk.LEFT, padx=5)
        ttk.Button(nav_frame, text="Next ▶", command=self.next_page).pack(side=tk.LEFT, padx=5)

        self.last_commit_label = ttk.Label(self.root, text="Last Commit: -")
        self.last_commit_label.pack(pady=(5, 0))

        self.rate_limit_label = ttk.Label(self.root, text="")
        self.rate_limit_label.pack(pady=(5, 0))

        self.profile_link = ttk.Label(self.root, text="", style="Link.TLabel")
        self.profile_link.pack()
        self.profile_link.bind("<Button-1>", self.open_user_profile)

        self.status_label = ttk.Label(self.root, text="Enter a username or org and click 'Get Repos'.", style="Dim.TLabel")
        self.status_label.pack(pady=5, fill=tk.X, padx=10)

        s = ttk.Style()
        s.configure("Link.TLabel", foreground="blue")
        s.map("Link.TLabel", foreground=[('active', 'red')])
        s.configure("Dim.TLabel", foreground="gray")

        self.build_insights_tab()

    def build_insights_tab(self):
        for c in self.insights_tab.winfo_children():
            c.destroy()
        header = ttk.Frame(self.insights_tab)
        header.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header, text="Insights Dashboard", font=("TkDefaultFont", 14, "bold")).pack(side=tk.LEFT)
        self.insights_summary = ttk.Label(header, text="")
        self.insights_summary.pack(side=tk.LEFT, padx=10)
        self.insights_container = ttk.Frame(self.insights_tab)
        self.insights_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.insights_container.grid_columnconfigure(0, weight=1)
        self.insights_container.grid_columnconfigure(1, weight=1)
        self.insights_container.grid_rowconfigure(0, weight=1)
        self.insights_container.grid_rowconfigure(1, weight=1)

    def bind_shortcuts(self):
        self.root.bind('<Return>', self.start_repo_fetch)
        self.root.bind('<Control-c>', self.copy_repo_url_to_clipboard)

    def start_repo_fetch(self, event: Optional[tk.Event] = None) -> None:
        """Start fetching repositories for the entered username."""
        logger.info("Starting repository fetch")
        
        # Clear previous data
        self.all_repos.clear()
        self.filtered_repos.clear()
        self.tree.delete(*self.tree.get_children())
        self.last_commit_label.config(text="Last Commit: -")
        self.profile_link.config(text="")
        self.profile_link_url = ""
        self.avatar_label.config(image=None)
        self.avatar_image = None  # Clear reference to prevent memory leaks
        
        # Clear the queue
        while not self.repo_queue.empty():
            try:
                self.repo_queue.get_nowait()
            except Empty:
                break
                
        threading.Thread(target=self.fetch_repos_worker, daemon=True).start()

    def fetch_repos_worker(self) -> None:
        """Worker thread for fetching repositories."""
        try:
            username = self.user_entry.get().strip()
            
            # Validate username input
            is_valid, error_msg = self._validate_username(username)
            if not is_valid:
                logger.warning(f"Invalid username input: {error_msg}")
                messagebox.showwarning("Invalid Input", error_msg)
                return
                
            logger.info(f"Fetching repositories for user: {username}")
            
            self.repo_queue.put(("status", "Checking GitHub status..."))
            self.repo_queue.put(("progress", "start"))
            
            # Check GitHub status
            status_ok, status_desc = self.api.check_status()
            if not status_ok:
                logger.warning(f"GitHub status issue: {status_desc}")
                messagebox.showwarning("GitHub Status", f"⚠ GitHub may be experiencing issues: {status_desc}")
            
            # Fetch user profile
            self.repo_queue.put(("status", f"Fetching profile for '{username}'..."))
            user_result = self.api.get_user(username)
            
            if not user_result["success"]:
                logger.error(f"Failed to fetch user profile: {user_result.get('message', 'Unknown error')}")
                self.repo_queue.put(("error", user_result))
                return
                
            user_data = user_result["data"]
            if not isinstance(user_data, dict):
                logger.error(f"Invalid user data format: {type(user_data)}")
                self.repo_queue.put(("error", {"success": False, "message": "Invalid user data format"}))
                return
                
            entity_type = user_data.get("type", "User")
            logger.info(f"Found {entity_type.lower()}: {username}")
            
            self.repo_queue.put(("profile", user_data))
            self.repo_queue.put(("rate_limit", None))
            
            # Stream repositories
            self.repo_queue.put(("status", f"Streaming repositories for '{username}'..."))
            repo_count = 0
            
            for page_result in self.api.stream_user_repos(username, entity_type):
                if not page_result["success"]:
                    logger.error(f"Error streaming repositories: {page_result.get('message', 'Unknown error')}")
                    self.repo_queue.put(("error", page_result))
                    return
                    
                repo_data = page_result["data"]
                if isinstance(repo_data, list):
                    repo_count += len(repo_data)
                    logger.debug(f"Processed {len(repo_data)} repositories (total: {repo_count})")
                    
                self.repo_queue.put(("repos", repo_data))
                self.repo_queue.put(("rate_limit", None))
                
            logger.info(f"Successfully fetched {repo_count} repositories for {username}")
            self.repo_queue.put(("done", None))
            
        except Exception as e:
            error_msg = f"Unexpected error during repository fetch: {e}"
            logger.error(error_msg, exc_info=True)
            self.repo_queue.put(("error", {"success": False, "message": error_msg}))
            self.repo_queue.put(("progress", "stop"))

    def process_repo_queue(self):
        try:
            for _ in range(10):
                msg_type, data = self.repo_queue.get_nowait()
                if msg_type == "profile":
                    self.profile_link.config(text=f"Profile: {data['html_url']}")
                    self.profile_link_url = data['html_url']
                    threading.Thread(target=self.load_avatar, args=(data['avatar_url'],), daemon=True).start()
                elif msg_type == "repos":
                    self.all_repos.extend(data)
                    self.filter_repos(reset_page=False)
                elif msg_type == "status":
                    self.update_status(data)
                elif msg_type == "progress":
                    if data == "start":
                        self.progress_bar.pack(fill=tk.X, padx=10, pady=(0, 5))
                        self.progress_bar.start()
                    else:
                        self.progress_bar.stop()
                        self.progress_bar.pack_forget()
                elif msg_type == "error":
                    self.handle_api_error(data)
                elif msg_type == "done":
                    self.repo_queue.put(("progress", "stop"))
                    self.update_last_commit_info()
                    self.update_status(f"Finished. Loaded {len(self.all_repos)} repositories.")
                    self.update_insights()
                elif msg_type == "rate_limit":
                    self.update_rate_limit_display()
        except Empty:
            pass
        finally:
            self.root.after(100, self.process_repo_queue)

    def handle_api_error(self, result):
        self.repo_queue.put(("progress", "stop"))
        status_code = result.get("status_code")
        message = result.get("message", "An unknown error occurred.")
        if status_code == 404:
            messagebox.showerror("Not Found", f"GitHub user/org '{self.user_entry.get().strip()}' not found.")
        elif status_code == 403:
            reset_time_str = self.api.rate_limit_reset_time.strftime('%H:%M:%S') if self.api.rate_limit_reset_time else "unknown"
            messagebox.showerror("Rate Limit", f"GitHub API rate limit reached. Your limit will reset at {reset_time_str}. Check your PAT or wait for the limit to reset.")
        elif status_code == 401:
            messagebox.showerror("Unauthorized", "Invalid or missing GitHub Personal Access Token.")
        else:
            messagebox.showerror("API Error", f"An error occurred: {message}")
        self.update_status(f"Error: {message}")
        self.update_rate_limit_display()

    def load_avatar(self, url: str) -> None:
        """Load and display user avatar from URL."""
        if not url or not isinstance(url, str):
            logger.warning("Invalid avatar URL provided")
            return
            
        logger.debug(f"Loading avatar from: {url}")
        
        try:
            # Validate URL format
            if not url.startswith(('http://', 'https://')):
                logger.warning(f"Avatar URL doesn't start with http(s): {url}")
                return
                
            # Set timeout for avatar loading
            with urllib.request.urlopen(url, timeout=10) as response:
                if response.status != 200:
                    logger.warning(f"Avatar request returned status {response.status}")
                    return
                    
                content_type = response.headers.get('Content-Type', '')
                if not content_type.startswith('image/'):
                    logger.warning(f"Avatar URL returned non-image content: {content_type}")
                    return
                    
                image_data = response.read()
                
            if not image_data:
                logger.warning("Avatar image data is empty")
                return
                
            # Process the image
            image = Image.open(io.BytesIO(image_data))
            
            # Verify it's a valid image
            image.verify()
            
            # Reopen for processing (verify() closes the image)
            image = Image.open(io.BytesIO(image_data))
            
            # Use appropriate resampling filter
            try:
                resample_filter = Image.Resampling.LANCZOS
            except AttributeError:
                resample_filter = Image.LANCZOS
                
            # Resize avatar
            image = image.resize((40, 40), resample_filter)
            
            # Convert to PhotoImage and display
            self.avatar_image = ImageTk.PhotoImage(image)
            self.avatar_label.config(image=self.avatar_image)
            
            logger.debug("Avatar loaded successfully")
            
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP error loading avatar: {e.code} {e.reason}")
        except urllib.error.URLError as e:
            logger.error(f"URL error loading avatar: {e.reason}")
        except OSError as e:
            logger.error(f"OS error loading avatar: {e}")
        except (IOError, SyntaxError) as e:
            logger.error(f"Image processing error for avatar: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading avatar: {e}", exc_info=True)

    def filter_repos(self, event=None, reset_page=True):
        search_term = self.search_entry.get().lower()
        if search_term:
            self.filtered_repos = [repo for repo in self.all_repos if search_term in repo['name'].lower()]
        else:
            self.filtered_repos = self.all_repos
        if reset_page:
            self.current_page = 0
        self.display_repos_page()

    def display_repos_page(self):
        selected_item_id = self.tree.selection()[0] if self.tree.selection() else None
        self.tree.delete(*self.tree.get_children())
        start = self.current_page * self.page_size
        end = start + self.page_size
        page_repos = self.filtered_repos[start:end]
        for repo in page_repos:
            self.tree.insert("", "end", iid=repo["name"], values=(
                repo["name"],
                repo.get("stargazers_count", 0),
                repo.get("forks_count", 0),
                repo.get("language", "-"),
                (repo.get("description") or "-").replace('\n', ' '),
            ))
        if selected_item_id and self.tree.exists(selected_item_id):
            self.tree.selection_set(selected_item_id)
            self.tree.see(selected_item_id)
        total_pages = (len(self.filtered_repos) + self.page_size - 1) // self.page_size or 1
        self.update_status(f"Page {self.current_page + 1}/{total_pages} | Displaying {len(self.filtered_repos)} of {len(self.all_repos)} loaded repos.")

    def update_last_commit_info(self):
        if not self.all_repos:
            return
        latest_commit = max(
            (datetime.strptime(repo['pushed_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc)
             for repo in self.all_repos if repo.get('pushed_at')),
            default=None
        )
        if latest_commit:
            local_tz = datetime.now().astimezone().tzinfo
            self.last_commit_label.config(text=f"Last Commit: {latest_commit.astimezone(local_tz).strftime('%Y-%m-%d %H:%M:%S %Z')}")

    def next_page(self):
        total_pages = (len(self.filtered_repos) + self.page_size - 1) // self.page_size
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.display_repos_page()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_repos_page()

    def sort_by_column(self, column_key):
        if not self.filtered_repos:
            return
        is_descending = self.sort_state.get("column") == column_key and not self.sort_state.get("descending", False)
        self.sort_state = {"column": column_key, "descending": is_descending}
        self.filtered_repos.sort(key=lambda repo: (repo.get(column_key) or 0) if isinstance(repo.get(column_key), int) else (repo.get(column_key) or "").lower(), reverse=is_descending)
        self.current_page = 0
        self.display_repos_page()

    def show_context_menu(self, event):
        selected_item_id = self.tree.identify_row(event.y)
        if not selected_item_id:
            return
        self.tree.selection_set(selected_item_id)
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label="Open in Browser", command=self.open_selected_repo_web)
        context_menu.add_command(label="Copy Clone URL", command=self.copy_repo_url_to_clipboard)
        context_menu.add_separator()
        context_menu.add_command(label="Clone Repository...", command=self.threaded_clone_repo)
        context_menu.tk_popup(event.x_root, event.y_root)

    def toggle_theme(self):
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        try:
            self.root.tk.call("set_theme", self.current_theme)
            set_key(CONFIG_FILE, "UI_THEME", self.current_theme)
        except tk.TclError:
            messagebox.showerror("Theme Error", "Azure theme files could not be loaded.")

    def update_status(self, message):
        self.status_label.config(text=message)

    def update_rate_limit_display(self):
        if self.api.rate_limit_remaining is not None:
            self.rate_limit_label.config(text=f"API Requests Remaining: {self.api.rate_limit_remaining}")

    def open_user_profile(self, event):
        if self.profile_link_url:
            webbrowser.open_new(self.profile_link_url)

    def open_selected_repo_web(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        repo_name = self.tree.item(selection[0])['values'][0]
        username = self.user_entry.get().strip()
        url = f"https://github.com/{username}/{repo_name}"
        webbrowser.open_new(url)

    def copy_repo_url_to_clipboard(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        repo_name = self.tree.item(selection[0])['values'][0]
        username = self.user_entry.get().strip()
        url = f"https://github.com/{username}/{repo_name}.git"
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self.update_status(f"Copied clone URL for {repo_name}")

    def threaded_clone_repo(self, event: Optional[tk.Event] = None) -> None:
        """Start cloning a repository in a separate thread."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a repository to clone.")
            return
            
        try:
            repo_name = self.tree.item(selection[0])['values'][0]
            if not repo_name:
                messagebox.showerror("Invalid Selection", "Selected repository has no name.")
                return
        except (IndexError, KeyError) as e:
            logger.error(f"Error getting repository name: {e}")
            messagebox.showerror("Selection Error", "Could not get repository name from selection.")
            return
            
        folder = filedialog.askdirectory(title="Choose folder to clone into")
        if not folder:
            return
            
        # Validate the selected folder
        is_valid, error_msg = self._validate_file_path(folder)
        if not is_valid:
            messagebox.showerror("Invalid Directory", error_msg)
            return
            
        logger.info(f"Starting clone of {repo_name} to {folder}")
        threading.Thread(target=self.clone_repo, args=(repo_name, folder), daemon=True).start()

    def clone_repo(self, repo_name: str, folder: str) -> None:
        """Clone a repository to the specified folder."""
        try:
            username = self.user_entry.get().strip()
            if not username:
                logger.error("No username available for cloning")
                messagebox.showerror("Error", "No username available for cloning.")
                return
                
            # Validate inputs
            if not repo_name or not isinstance(repo_name, str):
                logger.error(f"Invalid repository name: {repo_name}")
                messagebox.showerror("Error", "Invalid repository name.")
                return
                
            repo_url = f"https://github.com/{username}/{repo_name}.git"
            clone_path = os.path.join(folder, repo_name)
            
            # Check if destination already exists
            if os.path.exists(clone_path):
                logger.warning(f"Clone destination already exists: {clone_path}")
                messagebox.showerror("Exists", f"The destination path '{clone_path}' already exists.")
                return
                
            logger.info(f"Cloning {repo_url} to {clone_path}")
            self.repo_queue.put(("progress", "start"))
            self.repo_queue.put(("status", f"Cloning '{repo_name}'..."))
            
            # Clone the repository
            git.Repo.clone_from(repo_url, clone_path)
            
            logger.info(f"Successfully cloned {repo_name}")
            messagebox.showinfo("Success", f"Repository '{repo_name}' cloned to:\n{folder}")
            
        except git.exc.GitCommandError as e:
            error_msg = f"Git error while cloning {repo_name}: {e}"
            logger.error(error_msg)
            
            if hasattr(e, 'stderr') and e.stderr:
                stderr = e.stderr.lower()
                if "repository not found" in stderr:
                    msg = f"The repository '{repo_name}' could not be found or is not accessible."
                elif "permission denied" in stderr:
                    msg = f"Permission denied while cloning '{repo_name}'. Check your access rights."
                elif "authentication failed" in stderr:
                    msg = f"Authentication failed for '{repo_name}'. The repository may be private."
                else:
                    msg = f"Git error occurred while cloning:\n\n{e.stderr}"
            else:
                msg = f"Git command failed: {e}"
                
            messagebox.showerror("Clone Failed", msg)
            
        except OSError as e:
            error_msg = f"File system error while cloning {repo_name}: {e}"
            logger.error(error_msg)
            messagebox.showerror("Clone Failed", f"File system error: {e}")
            
        except Exception as e:
            error_msg = f"Unexpected error while cloning {repo_name}: {e}"
            logger.error(error_msg, exc_info=True)
            messagebox.showerror("Clone Failed", f"An unexpected error occurred: {e}")
            
        finally:
            self.repo_queue.put(("progress", "stop"))
            self.repo_queue.put(("status", f"Clone operation for '{repo_name}' finished."))

    def export_to_csv(self):
        if not self.filtered_repos:
            messagebox.showwarning("No Data", "There is no repository data to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", newline='', encoding="utf-8") as f:
                writer = csv.writer(f)
                headers = [self.tree.heading(col)["text"] for col in self.tree["columns"]]
                writer.writerow(headers)
                for repo in self.filtered_repos:
                    writer.writerow([
                        repo.get("name", ""),
                        repo.get("stargazers_count", 0),
                        repo.get("forks_count", 0),
                        repo.get("language", "-"),
                        (repo.get("description") or "-").replace('\n', ' '),
                    ])
            self.update_status(f"Successfully exported {len(self.filtered_repos)} repos to {path}")
        except Exception as e:
            logging.error(f"Export failed: {e}")
            messagebox.showerror("Export Failed", f"Failed to export CSV file:\n{e}")

    def update_insights(self):
        for c in self.insights_container.winfo_children():
            c.destroy()
        for cv in self.insight_canvases:
            try:
                cv.get_tk_widget().destroy()
            except Exception:
                pass
        self.insight_canvases = []

        total_repos = len(self.all_repos)
        total_stars = sum(r.get("stargazers_count", 0) for r in self.all_repos)
        total_forks = sum(r.get("forks_count", 0) for r in self.all_repos)
        self.insights_summary.config(text=f"Repos: {total_repos}  Stars: {total_stars}  Forks: {total_forks}")

        lang_counts = Counter((r.get("language") or "Unknown") for r in self.all_repos)
        top_langs = lang_counts.most_common(10)
        fig_lang = Figure(figsize=(5, 3), dpi=100)
        ax_lang = fig_lang.add_subplot(111)
        labels = [k for k, _ in top_langs]
        values = [v for _, v in top_langs]
        ax_lang.barh(labels[::-1], values[::-1])
        ax_lang.set_title("Top Languages")
        ax_lang.set_xlabel("Repo count")
        canvas_lang = FigureCanvasTkAgg(fig_lang, master=self.insights_container)
        canvas_lang.draw()
        canvas_lang.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.insight_canvases.append(canvas_lang)

        top_repos = sorted(self.all_repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:10]
        fig_stars = Figure(figsize=(5, 3), dpi=100)
        ax_stars = fig_stars.add_subplot(111)
        names = [r.get("name") for r in top_repos][::-1]
        stars = [r.get("stargazers_count", 0) for r in top_repos][::-1]
        ax_stars.barh(names, stars)
        ax_stars.set_title("Top Repos by Stars")
        ax_stars.set_xlabel("Stars")
        canvas_stars = FigureCanvasTkAgg(fig_stars, master=self.insights_container)
        canvas_stars.draw()
        canvas_stars.get_tk_widget().grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.insight_canvases.append(canvas_stars)

        now = datetime.utcnow().replace(day=1)
        months = [now - timedelta(days=30*i) for i in range(11, -1, -1)]
        month_labels = [m.strftime("%Y-%m") for m in months]
        counts = defaultdict(int)
        for r in self.all_repos:
            pa = r.get("pushed_at")
            if not pa:
                continue
            try:
                dt = datetime.strptime(pa, "%Y-%m-%dT%H:%M:%SZ")
                key = dt.replace(day=1).strftime("%Y-%m")
                counts[key] += 1
            except Exception:
                continue
        values = [counts.get(lbl, 0) for lbl in month_labels]
        fig_activity = Figure(figsize=(10, 3), dpi=100)
        ax_act = fig_activity.add_subplot(111)
        ax_act.plot(month_labels, values, marker="o")
        ax_act.set_title("Repo Activity (repos pushed per month)")
        ax_act.set_ylabel("Repos")
        ax_act.tick_params(axis='x', rotation=45)
        canvas_activity = FigureCanvasTkAgg(fig_activity, master=self.insights_container)
        canvas_activity.draw()
        canvas_activity.get_tk_widget().grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        self.insight_canvases.append(canvas_activity)

    def run(self) -> None:
        """Start the main application loop."""
        logger.info("Starting main application loop")
        self.root.mainloop()


def main() -> None:
    """Main entry point for the GitHub Repo Checker application."""
    try:
        logger.info("Starting GitHub Repo Checker application")
        
        # Create main window
        root = tk.Tk()
        root.withdraw()  # Hide initially
        
        # Set up basic error handling for Tkinter
        def handle_tk_error(exc, val, tb):
            logger.error(f"Tkinter error: {exc.__name__}: {val}", exc_info=(exc, val, tb))
            messagebox.showerror("Application Error", f"An unexpected error occurred:\n{val}")
        
        root.report_callback_exception = handle_tk_error
        
        # Show splash screen
        splash = SplashScreen(root)
        
        def main_app_setup() -> None:
            """Set up the main application after splash screen."""
            try:
                splash.close()
                root.deiconify()
                app = GitHubRepoChecker(root)
                logger.info("Application setup completed successfully")
            except Exception as e:
                logger.error(f"Failed to initialize main application: {e}", exc_info=True)
                messagebox.showerror(
                    "Initialization Error", 
                    f"Failed to start the application:\n{e}\n\nCheck the log file for details."
                )
                root.quit()
        
        # Delay main app setup to show splash screen
        root.after(3000, main_app_setup)  # Reduced from 8000ms to 3000ms
        
        # Start the application
        root.mainloop()
        
        logger.info("Application shutdown complete")
        
    except Exception as e:
        logger.critical(f"Critical error during application startup: {e}", exc_info=True)
        try:
            messagebox.showerror(
                "Critical Error", 
                f"Failed to start GitHub Repo Checker:\n{e}\n\nCheck the log file for details."
            )
        except:
            print(f"Critical error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
