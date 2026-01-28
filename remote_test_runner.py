
import paramiko
import sys
import time

HOST = "192.168.1.176"
USER = "user"
PASS = "01082008"
REMOTE_DIR = "home/user/test_con"

# Script to be executed on the remote machine
REMOTE_SCRIPT_CONTENT = """
import sys
import socket
import ssl
import time
import urllib.request
import subprocess

TARGET = "https://kinozal.tv"

print(f"--- Remote connectivity test from {socket.gethostname()} ---")

def test_socket_ssl():
    print(f"Testing remote TCP/SSL to {TARGET}...")
    try:
        context = ssl.create_default_context()
        with socket.create_connection(('kinozal.tv', 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname='kinozal.tv') as ssock:
                print(f"SSL Handshake OK. Cipher: {ssock.cipher()}")
                return True
    except Exception as e:
        print(f"SSL/TCP Failed: {e}")
        return False

def test_curl():
    print("Testing curl...")
    try:
        # -I for headers only to check connectivity
        subprocess.run(["curl", "-I", "-m", "10", TARGET], check=True)
        print("Curl success.")
    except Exception as e:
        print(f"Curl failed or not found: {e}")

if __name__ == "__main__":
    if test_socket_ssl():
        test_curl()
    else:
        print("Skipping curl because SSL handshake failed.")
"""

def main():
    print(f"Connecting to {HOST}...")
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, username=USER, password=PASS)
        
        print("Creating directory...")
        ssh.exec_command(f"mkdir -p {REMOTE_DIR}")
        
        print("Uploading test script...")
        sftp = ssh.open_sftp()
        with sftp.open(f"{REMOTE_DIR}/remote_check.py", 'w') as f:
            f.write(REMOTE_SCRIPT_CONTENT)
        sftp.close()
        
        print("Executing remote script...")
        stdin, stdout, stderr = ssh.exec_command(f"python3 {REMOTE_DIR}/remote_check.py")
        
        out = stdout.read().decode()
        err = stderr.read().decode()
        
        print("\n=== REMOTE OUTPUT ===")
        print(out)
        if err:
            print("=== REMOTE ERROR ===")
            print(err)
            
        ssh.close()
        
    except Exception as e:
        print(f"SSH Connection execution failed: {e}")

if __name__ == "__main__":
    main()
