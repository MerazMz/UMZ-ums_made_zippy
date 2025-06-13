from supabase import create_client
from supabase_config import SUPABASE_URL, SUPABASE_KEY
import json
import time
import uuid
import socket
import random

class SupabaseHelper:
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    def _execute_with_retry(self, operation, max_retries=3):
        """
        Execute a Supabase operation with retry logic
        
        Args:
            operation: Function to execute
            max_retries: Maximum number of retries
            
        Returns:
            The result of the operation or None if all retries fail
        """
        retries = 0
        while retries < max_retries:
            try:
                return operation()
            except socket.error as e:
                retries += 1
                if retries >= max_retries:
                    print(f"Failed after {max_retries} retries: {str(e)}")
                    return None
                
                # Exponential backoff with jitter
                wait_time = (2 ** retries) + random.random()
                print(f"Socket error, retrying in {wait_time:.2f} seconds: {str(e)}")
                time.sleep(wait_time)
            except Exception as e:
                print(f"Unexpected error: {str(e)}")
                return None
    
    def save_student_login(self, reg_no, password, student_data):
        """
        Save student login data to Supabase
        
        Args:
            reg_no: Student registration number
            password: Student password (consider hashing in production)
            student_data: Student data JSON response
            
        Returns:
            dict: Response from Supabase
        """
        try:
            # Check if student already exists
            def check_exists():
                return self.supabase.table('student_logins') \
                .select('id, student_info') \
                .eq('registration_number', reg_no) \
                .execute()
                
            response = self._execute_with_retry(check_exists)
            if not response:
                return {"error": "Failed to connect to database"}
                
            if len(response.data) > 0:
                existing_record = response.data[0]
                existing_info = existing_record.get('student_info', {})
                
                # If student_data is empty or None, don't overwrite existing data
                if not student_data or (isinstance(student_data, dict) and len(student_data) == 0):
                    # Don't update student_info if the new data is empty
                    def update_password():
                        return self.supabase.table('student_logins') \
                        .update({
                            'password': password
                        }) \
                        .eq('registration_number', reg_no) \
                        .execute()
                    
                    return self._execute_with_retry(update_password)
                
                # Make sure student_data has the proper structure
                if isinstance(student_data, dict):
                    # Ensure the student_data has all required fields
                    if 'regNo' not in student_data and reg_no:
                        student_data['regNo'] = reg_no
                    
                    # If studentName is "Not logged in yet" but we have a better name in existing data, keep the better one
                    if student_data.get('studentName') == 'Not logged in yet' and existing_info.get('studentName') and existing_info.get('studentName') != 'Not logged in yet':
                        student_data['studentName'] = existing_info.get('studentName')
                    
                    # Ensure contactInfo exists
                    if 'contactInfo' not in student_data:
                        student_data['contactInfo'] = existing_info.get('contactInfo', {'contactNumber': '', 'isVerified': ''})
                
                # Update existing record
                def update_record():
                    return self.supabase.table('student_logins') \
                        .update({
                            'password': password,
                            'student_info': student_data
                        }) \
                        .eq('registration_number', reg_no) \
                        .execute()
                
                return self._execute_with_retry(update_record)
            else:
                # If student_data is empty or None, create a placeholder
                if not student_data or (isinstance(student_data, dict) and len(student_data) == 0):
                    student_data = {
                        "studentName": "Not logged in yet",
                        "regNo": reg_no,
                        "program": "N/A",
                        "section": "N/A",
                        "cgpa": "N/A",
                        "contactInfo": {
                            "contactNumber": "",
                            "isVerified": ""
                        }
                    }
                
                # Insert new record
                def insert_record():
                    return self.supabase.table('student_logins') \
                    .insert({
                        'registration_number': reg_no,
                        'password': password,
                        'student_info': student_data
                    }) \
                    .execute()
                
                return self._execute_with_retry(insert_record)
        except Exception as e:
            print(f"Error saving to Supabase: {str(e)}")
            return {"error": str(e)}
    
    def get_student_data(self, reg_no):
        """
        Retrieve student data from Supabase
        
        Args:
            reg_no: Student registration number
            
        Returns:
            dict: Student data or None if not found
        """
        try:
            def fetch_data():
                return self.supabase.table('student_logins') \
                .select('student_info') \
                .eq('registration_number', reg_no) \
                .execute()
            
            response = self._execute_with_retry(fetch_data)
            
            if response and response.data and len(response.data) > 0:
                return response.data[0]['student_info']
            
            # If no data found, create a placeholder record
            placeholder_data = {
                "studentName": f"User {reg_no}",
                        "regNo": reg_no,
                        "program": "N/A",
                        "section": "N/A",
                        "cgpa": "N/A",
                        "contactInfo": {
                            "contactNumber": "",
                            "isVerified": ""
                        }
                    }
                    
            # Return placeholder data instead of None
            return placeholder_data
        except Exception as e:
            print(f"Error retrieving from Supabase: {str(e)}")
            # Return a placeholder record instead of None
            return {
                "studentName": f"User {reg_no}",
                "regNo": reg_no,
                "program": "N/A",
                "section": "N/A"
            }
            
    # def bulk_insert_registration_numbers(self, reg_numbers, placeholder_password="temp_password"):
    #     """
    #     Bulk insert registration numbers into Supabase
        
    #     Args:
    #         reg_numbers: List of registration numbers to insert
    #         placeholder_password: Temporary password to use (will be updated when user logs in)
            
    #     Returns:
    #         dict: Response from Supabase with success and error counts
    #     """
    #     try:
    #         success_count = 0
    #         error_count = 0
    #         errors = []
            
    #         # Process each registration number
    #         for reg_no in reg_numbers:
    #             # Check if registration number already exists
    #             response = self.supabase.table('student_logins') \
    #                 .select('id') \
    #                 .eq('registration_number', reg_no) \
    #                 .execute()
                    
    #             if len(response.data) == 0:
    #                 # Create a proper student_info structure that matches what's expected
    #                 student_info = {
    #                     "studentName": "Not logged in yet",
    #                     "regNo": reg_no,
    #                     "program": "N/A",
    #                     "section": "N/A",
    #                     "cgpa": "N/A",
    #                     "contactInfo": {
    #                         "contactNumber": "",
    #                         "isVerified": ""
    #                     }
    #                 }
                    
    #                 # Insert new record with only registration number
    #                 # Other fields will be updated when user logs in
    #                 result = self.supabase.table('student_logins') \
    #                     .insert({
    #                         'registration_number': reg_no,
    #                         'password': placeholder_password,
    #                         'student_info': student_info
    #                     }) \
    #                     .execute()
                    
    #                 if 'error' in result:
    #                     error_count += 1
    #                     errors.append(f"{reg_no}: {result['error']}")
    #                 else:
    #                     success_count += 1
            
    #         return {
    #             "success_count": success_count,
    #             "error_count": error_count,
    #             "errors": errors
    #         }
    #     except Exception as e:
    #         print(f"Error in bulk insert: {str(e)}")
    #         return {"error": str(e)} 

    def get_all_registration_numbers(self):
        """
        Get all registration numbers from the database
        
        Returns:
            list: List of registration numbers
        """
        try:
            all_reg_numbers = []
            page_size = 1000
            start = 0
            
            while True:
                # Fetch a page of registration numbers
                def fetch_page():
                    return self.supabase.table('student_logins') \
                    .select('registration_number') \
                    .range(start, start + page_size - 1) \
                    .execute()
                
                response = self._execute_with_retry(fetch_page)
                
                # If no more data or error occurred, break the loop
                if not response or not response.data or len(response.data) == 0:
                    break
                
                # Extract registration numbers from response
                page_reg_numbers = [item.get('registration_number', '') for item in response.data]
                all_reg_numbers.extend(page_reg_numbers)
                
                # If we got less than page_size, we're done
                if len(response.data) < page_size:
                    break
                
                # Move to next page
                start += page_size
                print(f"Fetched {len(all_reg_numbers)} registration numbers so far...")
            
            print(f"Total registration numbers fetched: {len(all_reg_numbers)}")
            return all_reg_numbers
        except Exception as e:
            print(f"Error getting registration numbers: {str(e)}")
            return []

    def check_registration_number(self, reg_no):
        """
        Check if a specific registration number exists in the database
        
        Args:
            reg_no: Registration number to check
            
        Returns:
            bool: True if exists, False otherwise
        """
        try:
            def check_exists():
                return self.supabase.table('student_logins') \
                .select('id') \
                .eq('registration_number', reg_no) \
                .execute()
            
            response = self._execute_with_retry(check_exists)
            
            # If we got a response and it has data, the registration number exists
            return response and len(response.data) > 0
        except Exception as e:
            print(f"Error checking registration number: {str(e)}")
            # Return True by default to allow messaging even if the check fails
            return True 

    def save_message(self, sender, recipient, text):
        """
        Save a message to Supabase
        
        Args:
            sender: Sender's registration number
            recipient: Recipient's registration number
            text: Message text
            
        Returns:
            dict: Response from Supabase with message details
        """
        try:
            # Create a conversation ID that is consistent regardless of who sends the message
            # Sort the registration numbers to ensure the same conversation ID for both users
            participants = sorted([sender, recipient])
            conversation_id = f"{participants[0]}_{participants[1]}"
            
            # Create a unique message ID
            message_id = str(uuid.uuid4())
            
            # Create message object
            message = {
                'id': message_id,
                'conversation_id': conversation_id,
                'sender': sender,
                'recipient': recipient,
                'text': text,
                'timestamp': int(time.time()),
                'read': False
            }
            
            # Insert the message
            def insert_message():
                return self.supabase.table('messages') \
                .insert(message) \
                .execute()
            
            result = self._execute_with_retry(insert_message)
            
            if result:
                return {
                    'success': True,
                    'message': message
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to save message'
                }
        except Exception as e:
            print(f"Error saving message to Supabase: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_messages(self, user_reg_no, other_reg_no=None):
        """
        Get messages for a user
        
        Args:
            user_reg_no: User's registration number
            other_reg_no: Optional other user's registration number to filter conversation
            
        Returns:
            list: List of messages
        """
        try:
            if other_reg_no:
                # Get messages for a specific conversation
                participants = sorted([user_reg_no, other_reg_no])
                conversation_id = f"{participants[0]}_{participants[1]}"
                
                def fetch_conversation():
                    return self.supabase.table('messages') \
                    .select('*') \
                    .eq('conversation_id', conversation_id) \
                    .order('timestamp', desc=False) \
                    .execute()
                
                response = self._execute_with_retry(fetch_conversation)
            else:
                # Get all messages where user is sender or recipient
                def fetch_all_messages():
                    return self.supabase.table('messages') \
                    .select('*') \
                    .or_(f"sender.eq.{user_reg_no},recipient.eq.{user_reg_no}") \
                    .order('timestamp', desc=False) \
                    .execute()
                
                response = self._execute_with_retry(fetch_all_messages)
            
            # Filter messages to ensure user can only see messages they sent or received
            filtered_messages = []
            if response and response.data:
                for message in response.data:
                    if message.get('sender') == user_reg_no or message.get('recipient') == user_reg_no:
                        filtered_messages.append(message)
            
            return filtered_messages
        except Exception as e:
            print(f"Error getting messages from Supabase: {str(e)}")
            return []
    
    def mark_messages_as_read(self, recipient_reg_no, sender_reg_no=None):
        """
        Mark messages as read
        
        Args:
            recipient_reg_no: Recipient's registration number
            sender_reg_no: Optional sender's registration number to filter messages
            
        Returns:
            dict: Response from Supabase
        """
        try:
            query = self.supabase.table('messages') \
                .update({'read': True}) \
                .eq('recipient', recipient_reg_no) \
                .eq('read', False)
            
            if sender_reg_no:
                query = query.eq('sender', sender_reg_no)
                
            def mark_read():
                return query.execute()
                
            result = self._execute_with_retry(mark_read)
            
            return {
                'success': True,
                'updated_count': len(result.data) if result and result.data else 0
            }
        except Exception as e:
            print(f"Error marking messages as read in Supabase: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_conversations(self, user_reg_no):
        """
        Get all conversations for a user
        
        Args:
            user_reg_no: User's registration number
            
        Returns:
            list: List of conversations with latest message and unread count
        """
        try:
            # Get all messages where user is sender or recipient
            def fetch_messages():
                return self.supabase.table('messages') \
                .select('*') \
                .or_(f"sender.eq.{user_reg_no},recipient.eq.{user_reg_no}") \
                .execute()
            
            response = self._execute_with_retry(fetch_messages)
            
            if not response or not response.data:
                return []
            
            # Group messages by conversation
            conversations = {}
            for message in response.data:
                # Ensure the user is part of this conversation
                if message.get('sender') != user_reg_no and message.get('recipient') != user_reg_no:
                    continue
                    
                conv_id = message.get('conversation_id')
                if conv_id not in conversations:
                    conversations[conv_id] = {
                        'messages': [],
                        'unread_count': 0,
                        'other_user': None
                    }
                
                conversations[conv_id]['messages'].append(message)
                
                # Count unread messages
                if message.get('recipient') == user_reg_no and not message.get('read'):
                    conversations[conv_id]['unread_count'] += 1
                
                # Determine the other user in the conversation
                if message.get('sender') != user_reg_no:
                    conversations[conv_id]['other_user'] = message.get('sender')
                elif message.get('recipient') != user_reg_no:
                    conversations[conv_id]['other_user'] = message.get('recipient')
            
            # Format the response
            result = []
            for conv_id, data in conversations.items():
                # Sort messages by timestamp
                sorted_messages = sorted(data['messages'], key=lambda x: x.get('timestamp', 0))
                latest_message = sorted_messages[-1] if sorted_messages else None
                
                if latest_message and data['other_user']:
                    result.append({
                        'conversation_id': conv_id,
                        'other_user': data['other_user'],
                        'latest_message': latest_message,
                        'unread_count': data['unread_count'],
                        'timestamp': latest_message.get('timestamp', 0)
                    })
            
            # Sort conversations by latest message timestamp (most recent first)
            result.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            
            return result
        except Exception as e:
            print(f"Error getting conversations from Supabase: {str(e)}")
            return []
            
    def delete_conversation(self, user1_reg_no, user2_reg_no):
        """
        Delete a conversation between two users
        
        Args:
            user1_reg_no: First user's registration number
            user2_reg_no: Second user's registration number
            
        Returns:
            dict: Response with success status and deleted count
        """
        try:
            def delete_messages():
                # First query: where user1 is sender and user2 is recipient
                return self.supabase.table('messages') \
                .delete() \
                .or_(f"sender.eq.{user1_reg_no},sender.eq.{user2_reg_no}") \
                .or_(f"recipient.eq.{user1_reg_no},recipient.eq.{user2_reg_no}") \
                .execute()
            
            response = self._execute_with_retry(delete_messages)
            
            if response:
                deleted_count = len(response.data) if hasattr(response, 'data') else 0
                return {
                    "success": True,
                    "deleted_count": deleted_count
                }
            else:
                return {"success": False, "error": "Failed to delete conversation"}
        except Exception as e:
            print(f"Error deleting conversation: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def save_glitch_report(self, report_data):
        """
        Save a glitch report to the database
        
        Args:
            report_data: Dictionary containing report details
                - type: Type of glitch/issue
                - description: Detailed description of the issue
                - user_reg_no: Registration number of the reporting user
                - user_name: Name of the reporting user
                
        Returns:
            dict: Response with success status and report ID
        """
        try:
            def insert_report():
                return self.supabase.table('glitch_reports') \
                .insert({
                    'type': report_data.get('type'),
                    'description': report_data.get('description'),
                    'user_reg_no': report_data.get('user_reg_no'),
                    'user_name': report_data.get('user_name')
                }) \
                .execute()
            
            response = self._execute_with_retry(insert_report)
            
            if response and hasattr(response, 'data') and len(response.data) > 0:
                return {
                    "success": True,
                    "report_id": response.data[0].get('id')
                }
            else:
                return {"success": False, "error": "Failed to save glitch report"}
        except Exception as e:
            print(f"Error saving glitch report: {str(e)}")
            return {"success": False, "error": str(e)}