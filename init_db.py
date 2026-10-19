from sqlalchemy import create_engine, text
from app.config import settings

def seed_database():
    engine = create_engine(settings.DATABASE_URL)
    is_sqlite = "sqlite" in settings.DATABASE_URL.lower()
    
    with engine.begin() as conn:
        if is_sqlite:
            conn.execute(text("DROP TABLE IF EXISTS enrollments;"))
            conn.execute(text("DROP TABLE IF EXISTS courses;"))
            conn.execute(text("DROP TABLE IF EXISTS students;"))
            conn.execute(text("DROP TABLE IF EXISTS departments;"))
        else:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            conn.execute(text("DROP TABLE IF EXISTS enrollments;"))
            conn.execute(text("DROP TABLE IF EXISTS courses;"))
            conn.execute(text("DROP TABLE IF EXISTS students;"))
            conn.execute(text("DROP TABLE IF EXISTS departments;"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))

        conn.execute(text("""
            CREATE TABLE departments (
                department_id INTEGER PRIMARY KEY,
                department_name VARCHAR(100) NOT NULL
            );
        """))

        conn.execute(text("""
            CREATE TABLE students (
                student_id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                department_id INTEGER NOT NULL,
                marks REAL,
                FOREIGN KEY (department_id) REFERENCES departments(department_id)
            );
        """))

        conn.execute(text("""
            CREATE TABLE courses (
                course_id INTEGER PRIMARY KEY,
                course_name VARCHAR(100) NOT NULL,
                department_id INTEGER NOT NULL,
                FOREIGN KEY (department_id) REFERENCES departments(department_id)
            );
        """))

        conn.execute(text("""
            CREATE TABLE enrollments (
                enrollment_id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                grade VARCHAR(5),
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (course_id) REFERENCES courses(course_id)
            );
        """))

        conn.execute(text("""
            INSERT INTO departments VALUES
            (1, 'Computer Science'),
            (2, 'Data Science'),
            (3, 'Mechanical Engineering'),
            (4, 'Electrical Engineering');
        """))

        conn.execute(text("""
            INSERT INTO students VALUES
            (101, 'Aarav Sharma', 1, 91.50),
            (102, 'Priya Patel', 1, 88.00),
            (103, 'Rohan Verma', 2, 74.20),
            (104, 'Ananya Iyer', 2, 95.80),
            (105, 'Karan Malhotra', 3, 62.00),
            (106, 'Sneha Reddy', 4, 83.50),
            (107, 'Vikram Das', 1, 69.40),
            (108, 'Neha Joshi', 3, 78.10);
        """))

        conn.execute(text("""
            INSERT INTO courses VALUES
            (201, 'Data Structures & Algorithms', 1),
            (202, 'Machine Learning', 2),
            (203, 'Thermodynamics', 3),
            (204, 'Digital Signal Processing', 4),
            (205, 'Database Management Systems', 1);
        """))

        conn.execute(text("""
            INSERT INTO enrollments VALUES
            (1, 101, 201, 'A+'),
            (2, 101, 205, 'A'),
            (3, 102, 201, 'A'),
            (4, 103, 202, 'B'),
            (5, 104, 202, 'A+'),
            (6, 105, 203, 'C'),
            (7, 106, 204, 'A'),
            (8, 108, 203, 'B+');
        """))

    print("[OK] Database setup complete with sample college records!")

if __name__ == "__main__":
    seed_database()
