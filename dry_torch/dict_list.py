from __future__ import annotations

from typing import Generic, TypeVar, Iterable, SupportsIndex, Self, Optional, NoReturn, overload, Hashable

import torch
from typing_extensions import override
from collections import UserList
from collections.abc import KeysView

from torch import Tensor

from .exceptions import ListKeyError, DifferentValueError, NotATensorError

K = TypeVar('K', bound=Hashable)  # Type variable for keys
V = TypeVar('V')  # Type variable for values


class DictList(UserList, Generic[K, V]):
    """
    A list-like data structure that stores dictionaries with a fixed set of keys.

    Args:
        iterable: An iterable of dictionaries to initialize the list with.

    Attributes:
        list_keys: A tuple of the keys that are present in the list.

    Methods:
        keys(): analogue of the keys method in dictionaries.
        get(key): analogue of the get method in dictionaries.
        to_dict(key): create a dictionary of list values.

    Raises:
        ListKeyError if the input dictionaries have keys that are not present in the list.

    """

    def __init__(self, iterable: Iterable[dict[K, V]] = zip(), /) -> None:
        self._list_keys: tuple[K, ...] = ()
        super().__init__(self._validate_iterable(iterable))

    @property
    def list_keys(self) -> tuple[K, ...]:
        return self._list_keys

    @list_keys.setter
    def list_keys(self, value=Iterable[K]):
        if self._list_keys:
            raise ListKeyError(self._list_keys, value)
        else:
            self._list_keys = tuple(value)
        return

    @list_keys.deleter
    def list_keys(self) -> NoReturn:
        raise AttributeError('Keys should never be deleted.')

    @override
    def __add__(self, other: Iterable[dict[K, V]], /) -> Self:
        out = self.copy()
        out.extend(other)
        return out

    @override
    @overload
    def __getitem__(self, index: SupportsIndex, /) -> dict[K, V]:
        ...

    @override
    @overload
    def __getitem__(self, input_slice: slice, /) -> Self:
        ...

    @override
    def __getitem__(self, index_or_slice: SupportsIndex | slice, /) -> dict[K, V] | Self:
        """
        Standard __getitem__ implementation that converts stored values back into dictionaries.
        """
        if isinstance(index_or_slice, slice):
            return self.__class__(map(self._item_to_dict, super().__getitem__(index_or_slice)))
        return self._item_to_dict(super().__getitem__(index_or_slice))

    @override
    def __setitem__(self, key, value):
        """
        Standard __setitem__ implementation that validates the input.
        """
        super().__setitem__(key, self._validate_dict(value))

    @override
    def __repr__(self) -> str:
        return f'DictList({self.to_dict().__repr__()}'

    @override
    def append(self, input_dict: dict[K, V], /) -> None:
        """
        Standard append implementation that validates the input.
        """
        super().append(self._validate_dict(input_dict))

    @override
    def extend(self, iterable: Iterable[dict[K, V]], /) -> None:
        """
        Standard extend implementation that validates the input.
        """
        if isinstance(iterable, self.__class__):  # prevents self-alimenting extension
            if self.list_keys == iterable.list_keys:  # more efficient implementation for the common case
                self.data.extend(iterable.data)
                return
        super().extend(self._validate_iterable(iterable))

    @override
    def insert(self, index: int, input_dict: dict[K, V], /):
        """
        Standard insert implementation that validates the input.
        """
        super().insert(index, self._validate_dict(input_dict))

    @override
    def pop(self, index: int = -1, /) -> dict[K, V]:
        """
        Standard pop implementation that converts stored values back into dictionaries.
        """
        return self._item_to_dict(super().pop(index))

    def keys(self) -> KeysView[K]:
        """
        Usual syntax for keys in a dictionary.
        """
        # workaround to produce a KeysView object
        return {key: None for key in self.list_keys}.keys()

    def get(self, key: K, /, default: Optional[V] = None) -> list[V] | list[None]:
        """
        Analogous to the get method in dictionaries.

        Args:
            key: The key for which to retrieve the values.
            default: The default value to return if the key is not present in the list.

        Returns:
            the values for the key in the list or a list of default values.
        """
        try:
            return [item[key] for item in self]
        except KeyError:
            if default is None:
                return [None] * len(self)
            return [default for _ in range(len(self))]  # make sure items are not the same object

    def _validate_dict(self, input_dict: dict[K, V], /) -> tuple[V, ...]:
        """
        Validate an input dictionary's keys.

        Args:
            input_dict: The input dictionary to validate.

        Side Effects:
            creates self.list_keys if it does not already exist.

        Returns:
            the values from the input dictionary ordered consistently with the existing keys.

        Raises:
            ListKeyError if the input dictionary has keys that are not present in the list.

        """
        if set(self.list_keys) != set(input_dict.keys()):
            self.list_keys = tuple(input_dict.keys())  # throws a ListKeyError if keys are already present.
        return tuple(input_dict[key] for key in self.list_keys)

    def _validate_iterable(self, iterable: Iterable[dict[K, V]], /) -> Iterable[tuple[V, ...]]:
        """
        Validate an iterable of input dictionaries.

        Args:
            iterable: the input iterable of dictionaries to validate.

        Returns:
            an iterable with validated dictionaries.
        """
        return map(self._validate_dict, iterable)

    def _item_to_dict(self, item: tuple) -> dict[K, V]:
        """
        Convert a stored item back into a dictionary.

        Returns:
            the dictionary corresponding to the item.
        """
        return dict(zip(self.list_keys, item))

    def to_dict(self) -> dict[K, list[V]]:
        """
        Convert the list into a dictionary.

        Returns:
            the dictionary representation of the list.
        """
        # more efficient than self.get
        return {key: [item[index] for item in self.data] for index, key in enumerate(self.list_keys)}


class TorchDictList(DictList[str, Tensor | list[Tensor]]):
    """
    Add support to a Dict List with Tensor and Tensor list values.

    Methods:
        from_batch: transforms batched Tensors into lists of Tensors referring to the same sample.
    """

    @classmethod
    def from_batch(cls,
                   tensor_dict_like: Iterable[tuple[str, Tensor | list[Tensor]]] | dict[str, Tensor | list[Tensor]],
                   indices: Optional[tuple[str, torch.LongTensor]] = None,
                   ) -> TorchDictList:
        """
        Instantiate the class so that each element has named tensor referring to the same sample.

        Args:
            tensor_dict_like: a dictionary or an iterable of named batched tensors.
            indices: a tuple containing the name of the dataset and the sampled indices, optional.
        """

        instance = cls()
        tensor_dict = dict(tensor_dict_like)
        if indices is not None:
            tensor_dict[indices[0] + "_indices"] = indices[1]
        instance.list_keys = tuple(tensor_dict.keys())
        instance.data = cls._enlist(tensor_dict.values())
        return instance

    @classmethod
    def _enlist(cls, tensor_iterable: Iterable[Tensor | list[Tensor]], /) -> list[tuple[Tensor | list[Tensor], ...]]:
        """
        Change the structure of batched Tensors and lists of Tensors.
        Args:
            tensor_iterable: an Iterable containing bathed tensors or lists of batched tensors.

        Return:
            a list containing a tuple of tensors and list of tensors for each element of the batch.
        """

        tensor_length = cls._tensors_len(tensor_iterable)
        return [tuple([item[i] for item in value] if isinstance(value, list) else value[i]
                      for value in tensor_iterable) for i in range(tensor_length)]

    @staticmethod
    def _tensors_len(tensor_iterable=Iterable[Tensor | list[Tensor]], /) -> int:
        """
        Check that all the contained tensors have the same length and return its value.
        Args:
            tensor_iterable: an Iterable containing bathed tensors or lists of batched tensors.
        Raises:
           DifferentLengthsError if the length of the lists and of the sub-lists is not the same.
           NotATensorError if items are note tensors or lists of tensors.
        Returns:
            only_len: the length of all the list and sub-lists.
        """
        if not tensor_iterable:
            return 0

        # this set should only have at most one element
        tensor_len_set: set[int] = set()

        for value in tensor_iterable:
            if isinstance(value, Tensor):
                tensor_len_set.add(len(value))
            elif isinstance(value, list):
                for elem in value:
                    if isinstance(elem, Tensor):
                        tensor_len_set.add(len(elem))
                    else:
                        raise NotATensorError(elem)
            else:
                raise NotATensorError(value)

        only_len, *other_len = tensor_len_set
        if other_len:
            raise DifferentValueError(tensor_len_set)
        return only_len
