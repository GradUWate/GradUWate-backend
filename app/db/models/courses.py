from sqlalchemy import String, Text, Integer, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..postgres.session import Base

class Course(Base):
    __tablename__ = "course"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    level: Mapped[int | None] = mapped_column(Integer)

class CourseTermRule(Base):
    __tablename__ = "course_term_rule"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    course_id: Mapped[str] = mapped_column(String, ForeignKey("course.id", ondelete="CASCADE"), nullable=False)
    season: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (CheckConstraint("season IN ('FALL','WINTER','SPRING')", name="ck_term_season"),)

class CourseConstraint(Base):
    __tablename__ = "course_constraint"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # reference the correct table name: "course" (not "courses")
    course_id: Mapped[str] = mapped_column(
        String, ForeignKey("course.id", ondelete="CASCADE"), nullable=False
    )

    kind: Mapped[str] = mapped_column(String, nullable=False)  # 'PREREQ' | 'ANTIREQ'
    target_course_id: Mapped[str] = mapped_column(String, nullable=False)
    group_id: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "kind",
            "target_course_id",
            "group_id",
            name="uq_course_constraint",
        ),
    )