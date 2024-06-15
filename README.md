GitHub Repo Checker
This project was inspired by the repository app-ideas by @florinpop17.

Overview
Originally designed to check the status of GitHub (whether it's UP or DOWN), this project has evolved into a tool that allows you to enter a GitHub username and view the user's last commit date and profile link. Additionally, you can click on any repository listed, and it will be automatically cloned into the same folder where this program is located.

Features
Check Last Commit Date: Enter a GitHub username and get the date of their last commit.
Profile Link: Provides a clickable link to the user's GitHub profile.
Clone Repositories: Click on any repository listed, and it will be cloned automatically.

User Interface

![image](https://github.com/Exill18/GitHUB-REPO-CHECKER/assets/108736956/d7a464d3-e2df-4c9c-83fd-fb9cf9c8b590)


How to Set Up
  1. Create Your Personal Access Token (PAT):
     <br>
     <a href="https://github.com/settings/tokens?type=beta">Go to GitHub Settings Tokens.</a> 
     <br>
     Create a token with the necessary permissions, including access to public repositories.
     <br>
  2. Create a .env File:
     <br>
    For security, store your PAT in a .env file (especially if you plan to place this on GitHub, even in a private repository).
     <br>
    Name your token variable GITHUB_PAT. For example:
     <br>
    <code class="!whitespace-pre hljs language-plaintext">GITHUB_PAT=your_personal_access_token_here</code>
     <br>
  3. Install Dependencies:
     <br>
    Install the necessary library to use the .env file:
    <br>
    <code class="!whitespace-pre hljs language-sh">pip install python-dotenv</code>
    <br>    
  4. Run the Project:
    You are now ready to run the project and check any public GitHub repositories and clone them as needed.



