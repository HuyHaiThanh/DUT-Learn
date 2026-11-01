from typing import Literal

from app.admin.schemas import ClassView


class MyClassView(ClassView):
    course_code: str
    course_name: str
    role: Literal["lecturer", "student"]
