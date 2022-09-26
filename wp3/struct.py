class Struct(object):
    """Simple class with user-supplied fields.

    This class works like a C-structure, with the advantage that fields are
    created dynamically upon construction.
    """
    def __init__(self, **kwargs):
        """Create a new structure with the given fields.

        Args:
            kwargs: list of keyword arguments. The keywords are added as fields
                of the structure, with the supplied initial value. As an
                example, one might write:
                ```
                clock = Struct(hours=16, minutes=47, seconds=22)
                print("The current time is:", f"{clock.hours}:{clock.minutes}:{clock.seconnds}")
                ```
                Which would print: `The current time is: 16:47:22`.
        """
        for k, v in kwargs.items():
            setattr(self, k, v)
