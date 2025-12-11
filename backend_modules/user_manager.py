import os
import json
from datetime import datetime

class UserManager:
    def __init__(self):
        self.users_dir = "users"
        self.users_file = os.path.join(self.users_dir, "users.json")
        self.ensure_directories()
        self.users = self.load_users()

    def ensure_directories(self):
        if not os.path.exists(self.users_dir):
            os.makedirs(self.users_dir)

    def load_users(self):
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: {self.users_file} is corrupted.")
                return {}
        return {}

    def save_users(self):
        try:
            with open(self.users_file, 'w') as f:
                json.dump(self.users, f, indent=2)
        except Exception as e:
            print(f"Error saving users: {e}")

    def add_user(self, username):
        if username not in self.users:
            self.users[username] = {
                'created_date': datetime.now().isoformat(),
                'model_path': os.path.join(self.users_dir, f"{username}_model"),
                'trained': False
            }
            self.save_users()
            return True
        return False

    def get_user(self, username):
        return self.users.get(username)

    def mark_user_trained(self, username):
        if username in self.users:
            self.users[username]['trained'] = True
            self.save_users()

    def list_users(self):
        return list(self.users.keys())
    
    def delete_user_model(self, username):
        if username in self.users:
            model_path = self.users[username]['model_path']
            model_file = f"{model_path}_model.h5"
            data_file = f"{model_path}_data.pkl"
            try:
                if os.path.exists(model_file): os.remove(model_file)
                if os.path.exists(data_file): os.remove(data_file)
                self.users[username]['trained'] = False
                self.save_users()
                return True
            except Exception as e:
                print(f"Error deleting model: {e}")
                return False
        return False