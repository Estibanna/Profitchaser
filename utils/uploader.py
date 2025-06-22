from ftplib import FTP

def upload_file_to_host(local_path, remote_path):
    ftp = FTP("ftp.edflipping.com")
    ftp.login(user="jouwgebruikersnaam", passwd="jouwwachtwoord")

    with open(local_path, "rb") as f:
        ftp.storbinary(f"STOR {remote_path}", f)

    ftp.quit()
