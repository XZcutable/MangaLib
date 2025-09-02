from enum import Enum

class Access(Enum):
    NONE = (0, 'none')
    USER = (1, 'user')
    MODERATOR = (2, 'moderator')
    ADMIN = (3, 'admin')
    OWNER = (4, 'owner')

    def toString(self):
        return str(self)
    
    def toNumber(self):
        return int(self)
    
    def fromString(str: str):
        match str:
            case Access.USER:
                return Access.USER
            case Access.MODERATOR:
                return Access.MODERATOR
            case Access.ADMIN:
                return Access.ADMIN
            case Access.OWNER:
                return Access.OWNER
            case _:
                return Access.NONE
    
    def __str__(self):
        return self.value[1]
    
    def __int__(self):
        return self.value[0]
    
    def __eq__(self, other):
        if other is None:
            return False

        if isinstance(other, int):
            return self.value[0] == other
        elif isinstance(other, str):
            return self.value[1].lower() == other.lower()
        elif isinstance(other, Access):
            return self == other.value[0] and self == other.value[1]
        else:
            raise TypeError('Invalid type for comparison')
        
    def __lt__(self, other):
        if isinstance(other, str):
            other = Access.fromString(other)
         
        if isinstance(other, int):
            return self.value[0] < other
        elif isinstance(other, Access):
            return self.value[0] < other.value[0]
        else:
            raise TypeError('Invalid type for comparison')

    def __le__(self, other):
        if isinstance(other, str):
            other = Access.fromString(other)
         
        if isinstance(other, int):
            return self.value[0] <= other
        elif isinstance(other, Access):
            return self.value[0] <= other.value[0]
        else:
            raise TypeError('Invalid type for comparison')

    def __gt__(self, other):
        if isinstance(other, str):
            other = Access.fromString(other)
        
        if isinstance(other, int):
            return self.value[0] > other
        elif isinstance(other, Access):
            return self.value[0] > other.value[0]
        else:
            raise TypeError('Invalid type for comparison')

    def __ge__(self, other):
        if isinstance(other, str):
            other = Access.fromString(other)
        
        if isinstance(other, int):
            return self.value[0] >= other
        elif isinstance(other, Access):
            return self.value[0] >= other.value[0]
        else:
            raise TypeError('Invalid type for comparison')
