def main():
    """Main program"""
    print("=" * 50)
    print("Student Grade Management System")
    print("=" * 50)
    
    # Get number of students
    count = get_student_count()
    
    # Get student data
    students = get_student_data(count)
    
    # Display report
    print_report(students)
    
    # Display statistics
    print_statistics(students)


def get_student_count():
    """Get valid number of students using while loop"""
    while True:
        try:
            count = int(input("\nHow many students? "))
            if count > 0 and count <= 10:
                return count
            else:
                print("Please enter a number between 1 and 10")
        except ValueError:
            print("Please enter a valid number")


def get_student_data(count):
    """Get data for each student using for loop"""
    students = []
    
    print(f"\nEnter data for {count} students:")
    print("-" * 50)
    
    for i in range(count):
        print(f"\nStudent #{i + 1}:")
        name = input("  Name: ")
        
        # Get 3 test scores
        scores = []
        for test_num in range(1, 4):
            while True:
                try:
                    score = int(input(f"  Test {test_num} score (0-100): "))
                    if 0 <= score <= 100:
                        scores.append(score)
                        break
                    else:
                        print("    Score must be between 0 and 100")
                except ValueError:
                    print("    Please enter a valid number")
        
        # Calculate average
        average = sum(scores) / len(scores)
        
        # Store student data
        student = {
            "name": name,
            "scores": scores,
            "average": average,
            "grade": calculate_grade(average)
        }
        students.append(student)
    
    return students


def calculate_grade(score):
    """Convert numeric score to letter grade"""
    if score >= 90:
        return 'A'
    elif score >= 80:
        return 'B'
    elif score >= 70:
        return 'C'
    elif score >= 60:
        return 'D'
    else:
        return 'F'


def print_report(students):
    """Print formatted student report"""
    print("\n" + "=" * 50)
    print("STUDENT GRADE REPORT")
    print("=" * 50)
    
    for student in students:
        print(f"\n{student['name']}")
        print(f"  Test Scores: {student['scores']}")
        print(f"  Average: {student['average']:.2f}")
        print(f"  Grade: {student['grade']}")


def print_statistics(students):
    """Print class statistics"""
    print("\n" + "=" * 50)
    print("CLASS STATISTICS")
    print("=" * 50)
    
    # Calculate class average
    all_averages = [s['average'] for s in students]
    class_avg = sum(all_averages) / len(all_averages)
    
    # Find highest and lowest
    highest = max(all_averages)
    lowest = min(all_averages)
    
    # Count grades
    grades = [s['grade'] for s in students]
    
    print(f"\nTotal Students: {len(students)}")
    print(f"Class Average: {class_avg:.2f}")
    print(f"Highest Average: {highest:.2f}")
    print(f"Lowest Average: {lowest:.2f}")
    
    print("\nGrade Distribution:")
    for grade in ['A', 'B', 'C', 'D', 'F']:
        count = grades.count(grade)
        if count > 0:
            print(f"  {grade}: {count} student(s)")


main()
```

---

## 🎮 Example Run:
```
==================================================
Student Grade Management System
==================================================

How many students? 3

Enter data for 3 students:
--------------------------------------------------

Student #1:
  Name: Alice
  Test 1 score (0-100): 95
  Test 2 score (0-100): 92
  Test 3 score (0-100): 98

Student #2:
  Name: Bob
  Test 1 score (0-100): 78
  Test 2 score (0-100): 82
  Test 3 score (0-100): 75

Student #3:
  Name: Charlie
  Test 1 score (0-100): 88
  Test 2 score (0-100): 90
  Test 3 score (0-100): 85

==================================================
STUDENT GRADE REPORT
==================================================

Alice
  Test Scores: [95, 92, 98]
  Average: 95.00
  Grade: A

Bob
  Test Scores: [78, 82, 75]
  Average: 78.33
  Grade: C

Charlie
  Test Scores: [88, 90, 85]
  Average: 87.67
  Grade: B

==================================================
CLASS STATISTICS
==================================================

Total Students: 3
Class Average: 87.00
Highest Average: 95.00
Lowest Average: 78.33

Grade Distribution:
  A: 1 student(s)
  B: 1 student(s)
  C: 1 student(s)