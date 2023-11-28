from typing import TypeVar, Any, Callable, Union, Type, Iterable, Generic, Literal
from collections import UserDict

T = TypeVar('T')  # typically torch.Tensor
# mypy not currently handling recursive annotations reliably
C = Union[list[T | 'C'], dict[Any, T | 'C'], T]  # nested list / dict that contains type T


def apply(struc: C, expected_type: Type[T], func: Callable[[T], T]) -> C:
    """
    It recursively looks for type T on lists or dictionaries and applies func.
    It can be used for changing device in structured (nested) formats.

    Args:
        struc: a structure that uses dictionaries values and lists as building blocks and stores
                objects of a type T
        expected_type: the type T that struc stores
        func: the function that modifies the objects (returns an object of type T)

    Returns:
        struc: a copy of the structure in the argument with the modified objects

    Raises:
        ValueError: struc stores objects of a different type than T when ignore_others is False
    """
    if isinstance(struc, list):
        return [apply(item, expected_type, func) for item in struc]
    elif isinstance(struc, dict):
        return {k: apply(v, expected_type, func) for k, v in struc.items()}
    elif isinstance(struc, expected_type):
        return func(struc)
    raise ValueError(f' Cannot apply {func} on Datatype {type(struc)}')


def dict_repr(struc: Any, max_length: int = 10) -> Any:
    """
    It represents objects by hierarchically expanding their dictionaries.
    To make sure that data does not end up in the config, it limits dict and list size.
    Classes are replaced with their names.

    Args:
        struc: a complex object with that may contain other objects
        max_length: limits the size of lists and dictionaries

    Returns:
        struc: a readable representation of an object
    """
    if isinstance(struc, (type, type(lambda: ...))):  # no builtin variable for the function class!
        return struc.__name__
    if isinstance(struc, (list, tuple)):
        if len(struc) > max_length:
            struc = struc[:max_length] + ['...']
    elif isinstance(struc, dict):
        return {k: struc.get(k, '') for k in dict_repr(list(struc))}  # limits dictionary size
    elif isinstance(struc, set):
        return {k for k in dict_repr(list(struc))}  # limits set size
    elif dct := getattr(struc, '__dict__', False):
        return {k: dict_repr(v, max_length) for k, v in ({'class': type(struc)} | dct).items()
                if v not in ({}, [], set())}  # filters out uninitialized attributes
    return struc


class DictList(UserDict, Generic[T]):
    """
    Dictionary with possibly nested lists of Iterables (specifically Tensors)
    """

    def __init__(self, **kwargs: dict[str, list[list[Iterable[T]]] | list[Iterable[T]]]):
        """
        Args: a dictionary that has strings as keys, and list (of lists) of objects of tipe T
        """
        super().__init__(**kwargs)
        self.info: dict = {}

    def __getitem__(self, key_or_index: int | str) -> list[list[Iterable[T]]] | list[Iterable[T]] | dict[Iterable[T]]:
        """
        It allows indexing by overloading __getitem__
        Args:
            key_or_index: a string for standard key mapping or an integer for indexing
        Returns:
            a dictionary of indexed lists (lists of lists) when indexing or standard mapping otherwise when indexing
        """
        if isinstance(key_or_index, int):
            return self._index_dict_list(key_or_index)  # indexing inside dict
        return super().__getitem__(key_or_index)  # standard dict mapping

    def _index_dict_list(self, ind: int) -> dict[T]:
        out_dict = {}
        for k, v in self.items():
            # if the list contains sub-lists, it indexes those
            if not v or isinstance(v[0], list):  # if v is empty assign []
                new_v = [elem[ind: ind + 1] for elem in v]  # keeps dims in Tensors
            else:
                new_v = v[ind: ind + 1]  # keeps dims in Tensors
            out_dict[k] = new_v
        return out_dict

    #
    def extend_dict(self, new_dict: dict[str, list[list[Iterable[T]]] | list[Iterable[T]] | Iterable[T]]):
        """
        It appends (or creates) dict of (nested) lists
        Args:
            new_dict: the dictionary that will extend self. If it maps to Iterables, those will be converted to lists
        Side Effect:
            the lists in self are extended
        """
        for key, value in new_dict.items():
            if isinstance(value, list):
                for elem, new_elem in zip(self.setdefault(key, [[] for _ in value]), value):
                    elem.extend(new_elem)
            else:
                self.setdefault(key, []).extend(value)  # transforms Tensor in list of Tensors
