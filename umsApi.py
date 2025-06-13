import requests
from bs4 import BeautifulSoup
import re
import json
import html
import urllib3

# Disable SSL warnings that will appear when verify=False is used
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_field(soup, name):
    field = soup.find("input", {"name": name})
    return field["value"] if field else ""


def get_hidden_inputs(soup):
    hidden_inputs = {}
    for input_tag in soup.find_all("input", {"type": "hidden"}):
        name = input_tag.get("name")
        value = input_tag.get("value", "")
        if name:
            hidden_inputs[name] = value
    return hidden_inputs


def get_assignments_data(session):
    try:
        base_url = "https://ums.lpu.in/lpuums/"
        assignment_url = base_url + "frmstudentdownloadassignment.aspx"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": assignment_url
        }

        # Get assignment page
        response = session.get(assignment_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Get all hidden inputs for post back
        hidden_inputs = get_hidden_inputs(soup)

        # Prepare "View All" button post data
        view_all_data = {
            "ctl00$cphHeading$Button1": "View All",
            **hidden_inputs
        }

        # Submit the "View All" post request
        response = session.post(assignment_url, data=view_all_data, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []

        # Theory assignments
        theory_table = soup.find('table', {'id': 'ctl00_cphHeading_rgAssignment_ctl00'})
        if theory_table:
            rows = theory_table.find_all('tr', {'class': ['rgRow', 'rgAltRow']})
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 11:
                    marks_obtained = cells[9].get_text(strip=True)
                    max_marks = cells[10].get_text(strip=True)
                    if marks_obtained and max_marks:
                        results.append({
                            "Course Code": cells[1].get_text(strip=True),
                            "Type": "Theory",
                            "Obtained Marks": marks_obtained,
                            "Total Marks": max_marks
                        })

        # Practical assignments
        practical_table = soup.find('table', {'id': 'ctl00_cphHeading_gvPracticalComponent_ctl00'})
        if practical_table:
            rows = practical_table.find_all('tr', {'class': ['rgRow', 'rgAltRow']})
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 18:
                    total_obtained = cells[16].get_text(strip=True)
                    total_max = cells[17].get_text(strip=True)
                    if total_obtained and total_max:
                        results.append({
                            "Course Code": cells[1].get_text(strip=True),
                            "Type": "Practical",
                            "Obtained Marks": total_obtained,
                            "Total Marks": total_max
                        })

        return results

    except Exception as e:
        print(f"[Assignment error]: {e}")
        return []


def get_attendance(session):
    url = "https://ums.lpu.in/lpuums/StudentDashboard.aspx/GetStudentCourses"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://ums.lpu.in/lpuums/StudentDashboard.aspx"
    }
    response = session.post(url, headers=headers, data="{}")
    html_content = json.loads(response.text)['d']
    soup = BeautifulSoup(html_content, "html.parser")
    attendance_data = []
    for course_div in soup.select(".mycoursesdiv"):
        attendance = course_div.select_one(".c100 span")
        course_name = course_div.select_one("p.font-weight-medium")
        if attendance and course_name:
            attendance_data.append({
                "course": course_name.text.strip(),
                "attendance": attendance.text.strip()
            })
    return attendance_data


def get_student_messages(session):
    url = "https://ums.lpu.in/lpuums/StudentDashboard.aspx/GetStudentMessages"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://ums.lpu.in/lpuums/StudentDashboard.aspx"
    }
    response = session.post(url, headers=headers, data="{}")
    html_content = json.loads(response.text)['d']
    soup = BeautifulSoup(html_content, "html.parser")
    messages = []
    for div in soup.select(".mycoursesdiv"):
        title = div.select_one(".font-weight-medium")
        body = div.select_one("p.text-small.text-muted")
        if title and body:
            messages.append({
                "title": title.text.strip(),
                "message": body.text.strip()
            })
    return messages


def get_student_contact(session):
    url = "https://ums.lpu.in/lpuums/StudentDashboard.aspx/GetStudentContactNo"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://ums.lpu.in/lpuums/StudentDashboard.aspx"
    }
    response = session.post(url, headers=headers, data="{}")
    contact_data = json.loads(response.text)['d']
    contact_parts = contact_data.split(":")
    return {
        "contact_number": contact_parts[0] if contact_parts else "",
        "is_verified": contact_parts[1] if len(contact_parts) > 1 else ""
    }


def clean_announcement_text(raw_html):
    """Clean and decode announcement HTML content"""
    if not raw_html:
        return ""
    try:
        decoded_html = html.unescape(raw_html)
        soup = BeautifulSoup(decoded_html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    except Exception as e:
        print(f"Error cleaning announcement text: {e}")
        return raw_html


def get_announcement_details(session, reg_no):
    url = "https://ums.lpu.in/lpuums/StudentDashboard.aspx/AnnouncementDetails"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://ums.lpu.in/lpuums/StudentDashboard.aspx",
        "Origin": "https://ums.lpu.in"
    }
    payload = {
        "LoginId": reg_no,
        "Type": "S"
    }

    try:
        response = session.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            print("Failed to fetch announcements.")
            return []

        data = response.json()
        announcements_raw = data.get("d", [])

        announcements = []
        for ann in announcements_raw:
            announcements.append({
                "subject": ann.get("subject", ""),
                "announcement": clean_announcement_text(ann.get("announcement", "")),
                "time": ann.get("time", ""),
                "date": ann.get("date", ""),
                "announcementid": ann.get("announcementid", ""),
                "uploadedby": ann.get("uploadedby", ""),
                "employeename": ann.get("employeename", "")
            })

        return announcements

    except Exception as e:
        print("Error while parsing announcements:", str(e))
        return []


def get_student_attendance_summary(session, dashboard_url):
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": dashboard_url
    }
    
    try:
        # First, access the dashboard page to simulate the user being on the page
        dashboard_response = session.get(dashboard_url, headers={"Referer": dashboard_url})
        dashboard_soup = BeautifulSoup(dashboard_response.text, 'html.parser')
        
        # Find the button that triggers the attendance summary request
        # This step is to ensure we follow the intended user flow
        info_button = dashboard_soup.find("i", {"class": "iconsminds-information"})
        
        if not info_button:
            # If the button isn't found, we can still attempt to get the data directly
            pass

        # Now, make the request to get the attendance summary
        summary_url = "https://ums.lpu.in/lpuums/StudentDashboard.aspx/StudentAttendanceSummary"
        response = session.post(summary_url, headers=headers, data="{}")
        response.raise_for_status()
        
        html_content = response.json()['d']
        
        # The HTML is malformed, with `<tr>` used as a separator.
        # We split the content by `<tr>` to get individual row data.
        row_chunks = html_content.split('<tr>')
        
        attendance_summary = []
        processed_courses = set()

        for chunk in row_chunks:
            if not chunk.strip():
                continue

            # Re-wrap the chunk in a table structure for proper parsing
            soup = BeautifulSoup(f"<table><tr>{chunk}</tr></table>", 'html.parser')
            cells = soup.find_all('td')

            if len(cells) >= 6:
                course_name = cells[0].get_text(strip=True)

                # Skip aggregate row and duplicates
                if "Aggregate Attendance" in course_name or course_name in processed_courses:
                    continue
                
                last_attended = cells[1].get_text(strip=True)
                duty_leaves = cells[2].get_text(strip=True)
                delivered = cells[3].get_text(strip=True)
                attended = cells[4].get_text(strip=True)
                
                attendance_summary.append({
                    "course_name": course_name,
                    "last_attended": last_attended,
                    "attended": attended,
                    "delivered": delivered,
                    "duty_leaves": duty_leaves
                })
                processed_courses.add(course_name)
                
        return attendance_summary
    except requests.exceptions.RequestException as e:
        print(f"Error fetching attendance summary: {e}")
        return []
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Error parsing attendance summary JSON: {e}")
        return []


def get_term_wise_marks(session):
    """
    Extract term-wise marks by simulating the iconsminds-information button click
    and processing the returned HTML content
    """
    url = "https://ums.lpu.in/lpuums/StudentDashboard.aspx/TermWiseMarks"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://ums.lpu.in/lpuums/StudentDashboard.aspx"
    }
    
    try:
        response = session.post(url, headers=headers, data="{}")
        response.raise_for_status()
        
        # Parse the JSON response
        json_data = response.json()
        html_content = json_data.get('d', '')
        
        # The HTML might be escaped in the JSON
        html_content = html.unescape(html_content)
        
        # Parse the HTML content
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Initialize the result structure
        term_wise_marks = []
        
        # Find all term sections
        term_sections = soup.find_all('a', {'class': 'btn btn-link collapsed text-left'})
        
        for section in term_sections:
            # Extract term ID from the section header
            term_id_match = re.search(r'Term Id : (\d+)', section.get_text(strip=True))
            term_id = term_id_match.group(1) if term_id_match else "Unknown"
            
            # Find the corresponding collapse div that contains the courses
            collapse_id = section.get('data-target', '')
            if not collapse_id:
                continue
                
            collapse_id = collapse_id.replace('#', '')
            collapse_div = soup.find('div', {'id': collapse_id})
            
            if not collapse_div:
                continue
                
            # Create a term object
            term_data = {
                "term_id": term_id,
                "courses": []
            }
            
            # Find all courses in this term
            course_sections = collapse_div.find_all('h4')
            
            for course_section in course_sections:
                course_name = course_section.get_text(strip=True)
                
                # Find the table that follows this course header
                table = course_section.find_next('table')
                if not table:
                    continue
                    
                course_data = {
                    "course_name": course_name,
                    "components": []
                }
                
                # Process rows in the table
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 3:  # Type, Marks, Weightage
                        component_type = cells[0].get_text(strip=True)
                        marks = cells[1].get_text(strip=True)
                        weightage = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                        
                        course_data["components"].append({
                            "type": component_type,
                            "marks": marks,
                            "weightage": weightage
                        })
                
                if course_data["components"]:
                    term_data["courses"].append(course_data)
            
            if term_data["courses"]:
                term_wise_marks.append(term_data)
        
        # If no term sections were found with the expected structure, try an alternative approach
        if not term_wise_marks:
            # Try to find term IDs directly
            term_id_matches = re.findall(r'collapse(\d+)', html_content)
            
            for term_id in term_id_matches:
                # Find all course sections for this term
                term_section = soup.find('div', {'id': f'collapse{term_id}'})
                
                if not term_section:
                    continue
                    
                term_data = {
                    "term_id": term_id,
                    "courses": []
                }
                
                # Find all h4 elements (course headers) in this term section
                course_headers = term_section.find_all('h4')
                
                for header in course_headers:
                    course_name = header.get_text(strip=True)
                    
                    # Find the table that follows this course header
                    table = header.find_next('table')
                    if not table:
                        continue
                        
                    course_data = {
                        "course_name": course_name,
                        "components": []
                    }
                    
                    # Process rows in the table
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) >= 3:  # Type, Marks, Weightage
                            component_type = cells[0].get_text(strip=True)
                            marks = cells[1].get_text(strip=True)
                            weightage = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                            
                            course_data["components"].append({
                                "type": component_type,
                                "marks": marks,
                                "weightage": weightage
                            })
                    
                    if course_data["components"]:
                        term_data["courses"].append(course_data)
                
                if term_data["courses"]:
                    term_wise_marks.append(term_data)
        
        return term_wise_marks
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching term-wise marks: {e}")
        return []
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Error parsing term-wise marks JSON: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error processing term-wise marks: {e}")
        return []


def login_and_fetch_all_result(reg_no, password):
    session = requests.Session()
    # Disable SSL certificate verification
    session.verify = False

    # Step 1: Get Login Page
    login_url = "https://ums.lpu.in/lpuums/"
    response = session.get(login_url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Step 2: Prepare Login Payload
    payload = {
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",
        "__VIEWSTATE": get_field(soup, "__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": get_field(soup, "__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": get_field(soup, "__EVENTVALIDATION"),
        "txtU": reg_no,
        "TxtpwdAutoId_8767": password,
        "iBtnLogins150203125": "Login"
    }

    # Step 3: Login
    post_response = session.post(login_url, data=payload)
    post_soup = BeautifulSoup(post_response.text, "html.parser")
    if post_soup.find("input", {"id": "TxtpwdAutoId_8767"}):
        return {"error": "Login failed. Check credentials."}

    # Step 4: Fetch Student Info
    student_info_url = "https://ums.lpu.in/lpuums/StudentDashboard.aspx/GetStudentBasicInformation"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest"
    }
    info_response = session.post(student_info_url, headers=headers, data="{}")
    student_info = {}
    try:
        info_json = info_response.json()
        student_list = info_json.get("d", [])
        if student_list and isinstance(student_list, list):
            student_info = {k: v for k, v in student_list[0].items()
                          if v not in [None, "", "null"] and k != "StudentPicture"}
    except:
        pass

    # Step 5: Get Result Page
    result_url = "https://ums.lpu.in/lpuums/frmStudentResult.aspx"
    result_response = session.get(result_url)
    result_soup = BeautifulSoup(result_response.text, "html.parser")

    # Step 6: Term-wise TGPA
    termwise_tgpa = []
    tds = result_soup.find_all("td", colspan="6")
    for td in tds:
        p = td.find("p")
        if p:
            match = re.search(r"TermId:\s*(\d+);\s*TGPA:\s*([\d.]+)", p.text.strip())
            if match:
                termwise_tgpa.append({
                    "term_id": match.group(1),
                    "tgpa": match.group(2)
                })

    # Step 7: Subject Grades
    subject_grades = []
    rows = result_soup.find_all("tr", {"class": ["rgRow", "rgAltRow"]})
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 5:
            course = cols[2].text.strip()
            credits = cols[3].text.strip()
            grade = cols[4].text.strip()
            if not course or len(course) < 5 or not re.match(r"^[A-F][+-]?$|^O$", grade):
                continue
            subject_grades.append({
                "course": course,
                "credits": credits,
                "grade": grade
            })

    # Step 8: Fetch Additional Data
    attendance = get_attendance(session)
    messages = get_student_messages(session)
    contact_info = get_student_contact(session)
    announcements = get_announcement_details(session, reg_no)
    assignments = get_assignments_data(session)
    dashboard_url = "https://ums.lpu.in/lpuums/StudentDashboard.aspx"
    attendance_summary = get_student_attendance_summary(session, dashboard_url)
    term_wise_marks = get_term_wise_marks(session)

    # Combine attendance data
    summary_map = {item['course_name']: item for item in attendance_summary}
    combined_attendance = []
    for att_item in attendance:
        course_name = att_item['course']
        summary_item = summary_map.get(course_name)

        if summary_item:
            combined_item = {
                "course": course_name,
                "attendance_percentage": att_item['attendance'],
                "last_attended": summary_item['last_attended'],
                "attended": summary_item['attended'],
                "delivered": summary_item['delivered'],
                "duty_leaves": summary_item['duty_leaves']
            }
            combined_attendance.append(combined_item)
        else:
            combined_attendance.append({
                "course": course_name,
                "attendance_percentage": att_item['attendance'],
                "last_attended": "N/A",
                "attended": "N/A",
                "delivered": "N/A",
                "duty_leaves": "N/A"
            })

    # Final Output
    output = {
        "student_info": student_info,
        "termwise_tgpa": termwise_tgpa,
        "subject_grades": subject_grades,
        "attendance": combined_attendance,
        "student_messages": messages,
        "contact_info": contact_info,
        "announcements": announcements,
        "assignments": assignments,
        "term_wise_marks": term_wise_marks
    }
    return output

# This section is commented out to allow the server to use the function directly
# If you want to test this script directly, uncomment the following lines:

# reg_no = input("Enter your registration number: ")
# password = input("Enter your password: ")
# result = login_and_fetch_all_result(reg_no, password)
# print(json.dumps(result, indent=4, ensure_ascii=False))