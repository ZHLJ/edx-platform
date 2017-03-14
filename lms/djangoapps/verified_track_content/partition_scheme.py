"""
UserPartitionScheme for enrollment tracks.
"""
from courseware.masquerade import (  # pylint: disable=import-error
    get_course_masquerade,
    get_masquerading_group_info,
    is_masquerading_as_specific_student,
)
from course_modes.models import CourseMode
from student.models import CourseEnrollment
from opaque_keys.edx.keys import CourseKey
from xmodule.partitions.partitions import NoSuchUserPartitionGroupError, Group, UserPartition


# These IDs are guaranteed to not overlap with Groups in the CohortUserPartition or the RandomUserPartitionScheme
# because CMS' course_group_config uses a minimum value of 100 for all generated IDs.
ENROLLMENT_GROUP_IDS = {
    CourseMode.AUDIT: 1,
    CourseMode.VERIFIED: 2,
    CourseMode.PROFESSIONAL: 3,
    CourseMode.NO_ID_PROFESSIONAL_MODE: 4,
    CourseMode.CREDIT_MODE: 5,
    CourseMode.HONOR: 6
}

class EnrollmentTrackUserPartition(UserPartition):

    @property
    def groups(self):
        # Note that when the key is stored during course_module creation, it is the draft version.
        course_key = CourseKey.from_string(self.parameters["course_id"]).for_branch(None)
        all_groups = []
        for mode in CourseMode.all_modes_for_courses([course_key])[course_key]:
            group = Group(ENROLLMENT_GROUP_IDS[mode.slug], unicode(mode.name))
            all_groups.append(group)

        return all_groups

    # # TODO: add test if this method stays in
    # def to_json(self):
    #     """
    #     'Serialize' to a json-serializable representation.
    #
    #     Returns:
    #         a dictionary with keys for the properties of the partition.
    #     """
    #     return {
    #         "id": self.id,
    #         "name": self.name,
    #         "scheme": self.scheme.name,
    #         "description": self.description,
    #         "parameters": self.parameters,
    #         "groups": [],  # Groups are obtained dynamically, so we don't need to persist them.
    #         "active": bool(self.active),
    #         "version": UserPartition.VERSION
    #     }


class EnrollmentTrackPartitionScheme(object):
    """
    This scheme uses learner enrollment tracks to map learners into partition groups.
    """

    @classmethod
    def get_group_for_user(cls, course_key, user, user_partition):
        """
        Returns the Group from the specified user partition to which the user
        is assigned, via enrollment mode.
        """
        # First, check if we have to deal with masquerading.
        # If the current user is masquerading as a specific student, use the
        # same logic as normal to return that student's group. If the current
        # user is masquerading as a generic student in a specific group, then
        # return that group.
        # TODO: this was copied from CohortPartitionScheme, may need some changes
        # This work will be done in a future story (ADD ticket number).
        if get_course_masquerade(user, course_key) and not is_masquerading_as_specific_student(user, course_key):
            group_id, user_partition_id = get_masquerading_group_info(user, course_key)
            if user_partition_id == user_partition.id and group_id is not None:
                try:
                    return user_partition.get_group(group_id)
                except NoSuchUserPartitionGroupError:
                    return None
            # The user is masquerading as a generic student. We can't show any particular group.
            return None

        if is_course_using_cohort_instead(course_key):
            return None
        mode_slug, is_active = CourseEnrollment.enrollment_mode_for_user(user, course_key)
        if mode_slug and is_active:
            course_mode = CourseMode.mode_for_course(course_key, mode_slug)
            if not course_mode:
                course_mode = CourseMode.DEFAULT_MODE
            return Group(ENROLLMENT_GROUP_IDS[course_mode.slug], unicode(course_mode.name))
        else:
            return None

    @classmethod
    def create_user_partition(cls, id, name, description, groups=None, parameters=None, active=True):
        return EnrollmentTrackUserPartition(id, name, description, [], cls, parameters, active)


def is_course_using_cohort_instead(course_key):
    """
    Returns whether the given course_context is using verified-track cohorts
    and therefore shouldn't use a track-based partition.
    """
    from verified_track_content.models import VerifiedTrackCohortedCourse
    return VerifiedTrackCohortedCourse.is_verified_track_cohort_enabled(course_key)