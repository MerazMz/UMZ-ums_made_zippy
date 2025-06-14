import sys
import io
import re
import requests
from flask import Flask, request, jsonify, send_from_directory
import os
from umsApi import login_and_fetch_all_result
from supabase_helper import SupabaseHelper

app = Flask(__name__)
supabase = SupabaseHelper()

# Serve static files
@app.route('/')
def index():
    return send_from_directory('.', 'login.html')

@app.route('/dashboard.html')
def dashboard():
    return send_from_directory('.', 'dashboard.html')

# Add route for static files
@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

# Login API endpoint
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    reg_no = data.get('regNo')
    password = data.get('password')
    
    if not reg_no or not password:
        return jsonify({'error': 'Registration number and password are required'}), 400
    
    try:
        # Call the API function directly
        result = login_and_fetch_all_result(reg_no, password)
        
        # Check if login failed
        if isinstance(result, dict) and 'error' in result and 'Login failed' in result['error']:
            return jsonify({"success": False, "message": "Invalid credentials"}), 401
        
        # Extract all data components
        student_info = result.get('student_info', {})
        termwise_tgpa = result.get('termwise_tgpa', [])
        subject_grades = result.get('subject_grades', [])
        assignments = result.get('assignments', [])
        attendance = result.get('attendance', [])
        messages = result.get('student_messages', [])
        contact_info = result.get('contact_info', {})
        announcements = result.get('announcements', [])
        attendance_summary = result.get('attendance_summary', [])
        term_wise_marks = result.get('term_wise_marks', [])
        # Calculate total credits
        total_credits = 0
        for grade in subject_grades:
            try:
                credits_str = grade.get('credits', '0')
                # Extract only the numeric part from the credits string
                numeric_credits = re.search(r'\d+\.?\d*', credits_str)
                if numeric_credits:
                    total_credits += float(numeric_credits.group(0))
                else:
                    total_credits += 0 # Add 0 if no numeric part found
            except (ValueError, TypeError):
                pass
        
        # Format the data to match what the frontend expects
        formatted_data = {
            "studentName": student_info.get('StudentName', 'N/A'),
            "regNo": student_info.get('Registrationnumber', 'N/A'),
            "program": student_info.get('Program', 'N/A'),
            "section": student_info.get('Section', 'N/A'),
            "dateOfBirth": student_info.get('DateofBirth', 'N/A'),
            "aggAttendance": student_info.get('AggAttendance', 'N/A'),
            "cgpa": student_info.get('CGPA', 'N/A'),
            "rollNumber": student_info.get('RollNumber', 'N/A'),
            "pendingFee": student_info.get('PendingFee', 'N/A'),
            "totalCredits": str(total_credits),
            "termData": [
                {"termId": item.get('term_id', ''), "tgpa": item.get('tgpa', '')}
                for item in termwise_tgpa
            ],
            "grades": [
                {"course": item.get('course', ''), "credits": item.get('credits', ''), "grade": item.get('grade', '')}
                for item in subject_grades
            ],
            "assignments": assignments,
            "detailedAttendance": [
                {"course": item.get('course', ''), "attendance": item.get('attendance_percentage', '')}
                for item in attendance
            ],
            "attendance": attendance,
            "messages": [
                {"title": item.get('title', ''), "message": item.get('message', '')}
                for item in messages
            ],
            "contactInfo": {
                "contactNumber": contact_info.get('contact_number', ''),
                "isVerified": contact_info.get('is_verified', '')
            },
            "announcements": [
                {
                    "subject": item.get('subject', ''),
                    "announcement": item.get('announcement', ''),
                    "time": item.get('time', ''),
                    "date": item.get('date', ''),
                    "uploadedBy": item.get('uploadedby', ''),
                    "employeeName": item.get('employeename', '')
                }
                for item in announcements
            ],
            "attendanceSummary": attendance_summary,
            "term_wise_marks": term_wise_marks
        }
        
        # Create simplified data structure for database storage exactly as specified
        db_formatted_data = {
            "cgpa": student_info.get('CGPA', 'N/A'),
            "regNo": student_info.get('Registrationnumber', 'N/A'),
            "program": student_info.get('Program', 'N/A'),
            "section": student_info.get('Section', 'N/A'),
            "contactInfo": {
                "isVerified": contact_info.get('is_verified', ''),
                "contactNumber": contact_info.get('contact_number', '')
            },
            "studentName": student_info.get('StudentName', 'Not logged in yet')
        }
        
        # Save to Supabase
        supabase.save_student_login(reg_no, password, db_formatted_data)
        
        return jsonify({"success": True, "student_data": formatted_data})
    except Exception as e:
        # If API call fails, try to use cached data as fallback
        try:
            cached_data = supabase.get_student_data(reg_no)
            if cached_data:
                print(f"API call failed, using cached data for {reg_no}")
                return jsonify({"success": True, "student_data": cached_data, "source": "cache"})
        except:
            pass
            
        return jsonify({'error': 'Failed to fetch student data', 'details': str(e)}), 500


@app.route('/get-student-info', methods=['POST'])
def get_student_rank():
    data = request.json
    registration_number = data.get('registrationNumber')

    if not registration_number:
        return jsonify({'error': 'Registration number is required'}), 400

    try:
        response = requests.post('https://lpu-student-ranking.vercel.app/get-student-info/', json={'registrationNumber': registration_number})
        response.raise_for_status()  # Raise an exception for HTTP errors
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Failed to connect to rank service', 'details': str(e)}), 500

# Chat API endpoints
@app.route('/api/search-users', methods=['GET'])
def search_users():
    query = request.args.get('query', '')
    
    if not query or len(query) < 3:
        return jsonify({'error': 'Search query must be at least 3 characters'}), 400
    
    try:
        # Get all registration numbers
        all_reg_numbers = supabase.get_all_registration_numbers()
        
        # Filter registration numbers that contain the query
        matching_reg_numbers = [reg_no for reg_no in all_reg_numbers if query.lower() in reg_no.lower()]
        
        # Get student data for matching registration numbers
        results = []
        for reg_no in matching_reg_numbers[:10]:  # Limit to 10 results
            student_data = supabase.get_student_data(reg_no)
            if student_data:
                results.append({
                    'regNo': reg_no,
                    'studentName': student_data.get('studentName', 'Unknown'),
                    'program': student_data.get('program', 'N/A')
                })
        
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'error': 'Failed to search users', 'details': str(e)}), 500

@app.route('/api/send-message', methods=['POST'])
def send_message():
    data = request.json
    sender = data.get('sender')
    recipient = data.get('recipient')
    text = data.get('text')
    
    if not sender or not recipient or not text:
        return jsonify({'error': 'Sender, recipient, and text are required'}), 400
    
    try:
        # Check if recipient exists
        if not supabase.check_registration_number(recipient):
            return jsonify({'error': 'Recipient not found'}), 404
        
        # Save message
        result = supabase.save_message(sender, recipient, text)
        
        if result.get('success'):
            return jsonify({'success': True, 'message': result.get('message')})
        else:
            return jsonify({'error': 'Failed to send message', 'details': result.get('error')}), 500
    except Exception as e:
        return jsonify({'error': 'Failed to send message', 'details': str(e)}), 500

@app.route('/api/get-conversations', methods=['GET'])
def get_conversations():
    user_reg_no = request.args.get('regNo')
    
    if not user_reg_no:
        return jsonify({'error': 'Registration number is required'}), 400
    
    try:
        conversations = supabase.get_conversations(user_reg_no)
        return jsonify({'success': True, 'conversations': conversations})
    except Exception as e:
        return jsonify({'error': 'Failed to get conversations', 'details': str(e)}), 500

@app.route('/api/get-messages', methods=['GET'])
def get_messages():
    user_reg_no = request.args.get('regNo')
    other_reg_no = request.args.get('otherRegNo')
    
    if not user_reg_no or not other_reg_no:
        return jsonify({'error': 'Both registration numbers are required'}), 400
    
    try:
        messages = supabase.get_messages(user_reg_no, other_reg_no)
        
        # Mark messages as read
        supabase.mark_messages_as_read(user_reg_no, other_reg_no)
        
        return jsonify({'success': True, 'messages': messages})
    except Exception as e:
        return jsonify({'error': 'Failed to get messages', 'details': str(e)}), 500

@app.route('/api/delete-conversation', methods=['DELETE'])
def delete_conversation():
    user_reg_no = request.args.get('regNo')
    other_reg_no = request.args.get('otherRegNo')
    
    if not user_reg_no or not other_reg_no:
        return jsonify({'error': 'Both registration numbers are required'}), 400
    
    try:
        # Delete the conversation using the supabase helper
        result = supabase.delete_conversation(user_reg_no, other_reg_no)
        
        if result.get('success'):
            return jsonify({
                'success': True, 
                'message': 'Conversation deleted successfully',
                'deleted_count': result.get('deleted_count', 0)
            })
        else:
            return jsonify({'error': 'Failed to delete conversation', 'details': result.get('error')}), 500
    except Exception as e:
        return jsonify({'error': 'Failed to delete conversation', 'details': str(e)}), 500

@app.route('/api/report-glitch', methods=['POST'])
def report_glitch():
    data = request.json
    
    # Validate required fields
    if not data.get('type') or not data.get('description'):
        return jsonify({'error': 'Type and description are required'}), 400
    
    try:
        # Prepare report data
        report_data = {
            'type': data.get('type'),
            'description': data.get('description'),
            'user_reg_no': data.get('userInfo', {}).get('regNo', 'Unknown'),
            'user_name': data.get('userInfo', {}).get('name', 'Unknown User')
        }
        
        # Save the report to the database
        result = supabase.save_glitch_report(report_data)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Glitch report submitted successfully',
                'report_id': result.get('report_id')
            })
        else:
            return jsonify({'error': 'Failed to submit glitch report', 'details': result.get('error')}), 500
    except Exception as e:
        return jsonify({'error': 'Failed to submit glitch report', 'details': str(e)}), 500

@app.route('/api/get-student-info', methods=['GET'])
def get_student_info():
    reg_no = request.args.get('regNo')
    
    if not reg_no:
        return jsonify({'error': 'Registration number is required'}), 400
    
    try:
        # Get student data from Supabase
        student_data = supabase.get_student_data(reg_no)
        
        # We'll always return data now, even if it's a placeholder
        return jsonify(student_data)
    except Exception as e:
        print(f"Error in get_student_info: {str(e)}")
        # Return a placeholder record instead of an error
        return jsonify({
            "studentName": f"User {reg_no}",
            "regNo": reg_no,
            "program": "N/A",
            "section": "N/A"
        })

if __name__ == '__main__':
    # For local development only. In production, use gunicorn (see Procfile).
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)