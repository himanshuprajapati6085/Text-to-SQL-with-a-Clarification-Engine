from sqlalchemy import text

from app.services.db_manager import DBManager



def init_database():

    engine = DBManager.get_engine("college")

    with engine.begin() as conn:

        conn.execute(text("""

            CREATE TABLE IF NOT EXISTS departments (

                department_id INTEGER PRIMARY KEY AUTOINCREMENT,

                department_name VARCHAR(100) NOT NULL UNIQUE

            );

        """))



        conn.execute(text("""

            CREATE TABLE IF NOT EXISTS teachers (

                teacher_id INTEGER PRIMARY KEY AUTOINCREMENT,

                name VARCHAR(100) NOT NULL,

                subject VARCHAR(100),

                department_id INTEGER,

                email VARCHAR(120),

                FOREIGN KEY (department_id) REFERENCES departments(department_id)

            );

        """))



        conn.execute(text("""

            CREATE TABLE IF NOT EXISTS students (

                student_id INTEGER PRIMARY KEY AUTOINCREMENT,

                name VARCHAR(100) NOT NULL,

                department_id INTEGER,

                marks REAL,

                attendance REAL,

                FOREIGN KEY (department_id) REFERENCES departments(department_id)

            );

        """))



        conn.execute(text("""

            CREATE TABLE IF NOT EXISTS courses (

                course_id INTEGER PRIMARY KEY AUTOINCREMENT,

                course_name VARCHAR(100) NOT NULL,

                department_id INTEGER,

                teacher_id INTEGER,

                FOREIGN KEY (department_id) REFERENCES departments(department_id),

                FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id)

            );

        """))



        conn.execute(text("""

            CREATE TABLE IF NOT EXISTS enrollments (

                enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,

                student_id INTEGER NOT NULL,

                course_id INTEGER NOT NULL,

                grade VARCHAR(10),

                FOREIGN KEY (student_id) REFERENCES students(student_id),

                FOREIGN KEY (course_id) REFERENCES courses(course_id)

            );

        """))



    print("[OK] Clean SQLite database ready: college.db")



if __name__ == "__main__":

    init_database()
