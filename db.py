'''
db
database file, containing all the logic to interface with the sql database
'''

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models import *
import bcrypt

from pathlib import Path

# creates the database directory
Path("database") \
    .mkdir(exist_ok=True)

# "database/main.db" specifies the database file
# change it if you wish
# turn echo = True to display the sql output
engine = create_engine("sqlite:///database/main.db", echo=False)

# initializes the database
Base.metadata.create_all(engine)

# inserts a user to the database
def insert_user(username: str, password: str):

# Store the hashed_password in your database's user record

    with Session(engine) as session:

        user = User(username=username, password=password)
        session.add(user)
        session.commit()

# gets a user from the database
def get_user(username: str):
    with Session(engine) as session:
        return session.get(User, username)
    

def get_friends(username: str):
    with Session(engine) as session:
        # Fetch all accepted friend relationships where the given user is either the requester or the receiver
        accepted_friends = session.query(Friend).filter(
            ((Friend.requesting_username == username) | (Friend.receiving_username == username)),
            Friend.isAccepted == True
        ).all()

        # Fetch all pending friend requests sent to the user
        pending_requests = session.query(Friend).filter(
            Friend.receiving_username == username,
            Friend.isAccepted == False
        ).all()

        # Fetch all friend requests sent by the user that are not yet accepted
        pending_friends = session.query(Friend).filter(
            Friend.requesting_username == username,
            Friend.isAccepted == False
        ).all()

        # Construct a dictionary to organize the results
        result = {
            "accepted_friends": [],
            "pending_requests": [],
            "pending_friends": []
        }

        # Populate accepted friends list
        for friend in accepted_friends:
            if friend.requesting_username == username:
                # If the current user is the requester, add the receiver to the list
                friend_info = session.get(User, friend.receiving_username)
                result["accepted_friends"].append(friend_info)
            else:
                # If the current user is the receiver, add the requester to the list
                friend_info = session.get(User, friend.requesting_username)
                result["accepted_friends"].append(friend_info)

        # Populate pending requests list
        for request in pending_requests:
            requester_info = session.get(User, request.requesting_username)
            result["pending_requests"].append(requester_info)

        # Populate pending friends list
        for pending in pending_friends:
            receiver_info = session.get(User, pending.receiving_username)
            result["pending_friends"].append(receiver_info)

        return result


def add_friend_request(username: str, friend_username: str):
    with Session(engine) as session:
        # Check if the user and friend_username exist in the database
        user = session.get(User, username)
        friend_user = session.get(User, friend_username)

        # If either user doesn't exist, return an error
        if not user or not friend_user:
            return False, "User does not exist. Please check username, you can only request active usernames to be friends."

        # Check if the request already exists or if user is adding themselves
        existing_request = session.query(Friend).filter(
            ((Friend.requesting_username == username) & (Friend.receiving_username == friend_username)) |
            ((Friend.requesting_username == friend_username) & (Friend.receiving_username == username))
        ).first()

        if existing_request or username == friend_username:
            return False, "Request already exists or invalid request."

        new_friend_request = Friend(
            requesting_username=username,
            receiving_username=friend_username,
            isAccepted=False
        )
        session.add(new_friend_request)
        session.commit()
        return True, "Friend request sent successfully."


def handle_friend_request(username, friend_username, is_accepted):
    with Session(engine) as session:
        # Find the friend request
        friend_request = session.query(Friend).filter(
            Friend.requesting_username == friend_username,
            Friend.receiving_username == username
        ).first()

        if not friend_request:
            return False, "Friend request not found."

        if is_accepted:
            # Approve the friend request
            friend_request.isAccepted = True
            session.commit()
            return True, "Friend request approved."
        else:
            # Reject the friend request by deleting it
            session.delete(friend_request)
            session.commit()
            return True, "Friend request rejected."

