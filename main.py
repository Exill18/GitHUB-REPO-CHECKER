import tkinter as tk
import requests

class GitHubStatusApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub Status App")

        self.status_listbox = tk.Listbox(root, selectmode=tk.SINGLE)
        self.status_listbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.get_status_button = tk.Button(root, text="Get Status", command=self.get_github_status)
        self.get_status_button.pack(pady=5)

    def get_github_status(self):
        try:
            response = requests.get('https://www.githubstatus.com/api/v2/status.json')
            data = response.json()

            self.status_listbox.delete(0, tk.END)

            for component in data['components']:
                status = component['status']
                name = component['name']
                self.status_listbox.insert(tk.END, f"{name} - {status}")
        except requests.exceptions.RequestException as e:
            self.status_listbox.delete(0, tk.END)
            self.status_listbox.insert(tk.END, "Error fetching status")

if __name__ == "__main__":
    root = tk.Tk()
    app = GitHubStatusApp(root)
    root.mainloop()
