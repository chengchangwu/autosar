"""
Classes related to AUTOSAR Elements

"""

import re
from collections.abc import Iterable
from typing import Any, Union
from enum import Enum
import abc
import autosar.xml.enumeration as ar_enum


alignment_type_re = re.compile(
    r"[1-9][0-9]*|0[xX][0-9a-fA-F]*|0[bB][0-1]+|0[0-7]*|UNSPECIFIED|UNKNOWN|BOOLEAN|PTR")

display_format_str_re = re.compile(
    r"%[ \-+#]?[0-9]*(\.[0-9]+)?[diouxXfeEgGcs]")

# Type aliases

ValueSpeficationElement = Union["TextValueSpecification",
                                "NumericalValueSpecification",
                                "NotAvailableValueSpecification",
                                "ArrayValueSpecification",
                                "RecordValueSpecification",
                                "ApplicationValueSpecification",
                                "ConstantReference"]

# Helper classes


class NumericalValue:
    """
    Wrapper for numerical value
    """

    def __init__(self,
                 value: int | float | str,
                 value_format: ar_enum.ValueFormat = ar_enum.ValueFormat.DEFAULT
                 ) -> None:
        self._value = self._validate_value(value)
        if isinstance(value, str):
            if value.startswith("0x"):
                value_format = ar_enum.ValueFormat.HEXADECIMAL
            elif value.startswith("0b"):
                value_format = ar_enum.ValueFormat.BINARY
        self.value_format = value_format

    @property
    def value(self):
        """Value property"""
        return self._value

    @value.setter
    def value(self, value):
        self._value = self._validate_value(value)

    def _validate_value(self, value: Any) -> int | float | str:
        if isinstance(value, (int, float)):
            return value
        elif isinstance(value, str):
            try:
                return int(value, 0)
            except ValueError:
                return float(value)
        else:
            raise TypeError(f"Unexpected type for value {str(type(value))}")


class PositiveIntegerValue:
    """
    Wrapper for positive value
    """

    def __init__(self,
                 value: int,
                 value_format: ar_enum.ValueFormat = ar_enum.ValueFormat.DEFAULT
                 ) -> None:
        self._value = self._validate_value(value)
        self.value_format = value_format

    @property
    def value(self):
        """Value property"""
        return self._value

    @value.setter
    def value(self, value):
        self._value = self._validate_value(value)

    def _validate_value(self, value: int | str) -> int:
        if isinstance(value, str):
            try:
                value = int(value, 0)
            except ValueError as err:
                raise TypeError("Unable to convert to integer") from err
        if isinstance(value, int):
            if value < 0:
                raise ValueError("Value must be a positive integer")
            return value
        else:
            raise TypeError(f"Unexpected type for value {str(type(value))}")

# Base classes


class ARObject:
    """
    Base class for all AUTOSAR objects
    """

    @property
    def is_empty(self) -> bool:
        """
        True if no value has been set (everything is None)
        """
        for value in vars(self).values():
            if isinstance(value, list):
                if len(value) > 0:
                    return False
            else:
                if value is not None:
                    return False
        return True

    def is_empty_with_ignore(self, ignore_set: set) -> bool:
        """
        Same as is_empty but the caller can give
        a list of property names to ignore during
        check
        """
        for key in vars(self).keys():
            if key not in ignore_set:
                value = getattr(self, key)
                if isinstance(value, list):
                    if len(value) > 0:
                        return False
                else:
                    if value is not None:
                        return False
        return True

    def _assign_optional(self, attr_name: str, value: Any, type_name: type) -> None:
        """
        Same as _assign but with a None-check
        """
        if value is not None:
            self._assign(attr_name, value, type_name)

    def _assign(self, attr_name: str, value: Any, type_name: type) -> None:
        """
        Assign single value to attribute with type check.
        """
        if issubclass(type_name, Enum):
            self._set_attr_with_strict_type(attr_name, value, type_name)
        elif issubclass(type_name, BaseRef):
            self._set_attr_from_str_or_direct(attr_name, value, type_name)
        else:
            self._set_attr_with_type_cast(attr_name, value, type_name)

    def _assign_int_or_str_pattern_optional(self, attr_name: str, value: int | str | None, pattern: re.Pattern) -> None:
        """
        Same as _assign_int_or_str_pattern but with a None-check
        """
        if value is not None:
            self._assign_int_or_str_pattern(attr_name, value, pattern)

    def _assign_int_or_str_pattern(self, attr_name: str, value: int | str, pattern: re.Pattern) -> None:
        """
        Special assignment-function for values that can be either int or conforms
        to a specific regular expression
        """
        if isinstance(value, int):
            pass
        elif isinstance(value, str):
            match = pattern.match(value)
            if match is None:
                raise ValueError(f"Invalid parameter '{value}' for '{attr_name}'")
        else:
            raise TypeError(f"{attr_name}: Invalid type. Expected (int, str), got '{str(type(value))}'")
        setattr(self, attr_name, value)

    def _assign_optional_strict(self, attr_name: str, value: Any, type_name: type) -> None:
        """
        Sets object attribute with strict type check
        """
        if value is not None:
            self._set_attr_with_strict_type(attr_name, value, type_name)

    def _assign_optional_positive_int(self, attr_name, value: int) -> None:
        """
        Checks that the optional value is a positive integer before assignment
        """
        if value is not None:
            self._set_attr_positive_int(attr_name, value)

    def _set_attr_with_strict_type(self, attr_name: str, value: Any, type_class: type) -> None:
        """
        Sets object attribute only if the value is matches given type-class
        """
        if isinstance(value, type_class):
            setattr(self, attr_name, value)
        else:
            raise TypeError(
                f"Invalid type for parameter '{attr_name}'. Expected type {str(type_class)}, got {str(type(value))}")

    def _set_attr_from_str_or_direct(self, attr_name: str, value: Any, type_name: type):
        """
        Can create new objects from str if necessary
        """
        if isinstance(value, str):
            new_value = type_name(value)
        elif isinstance(value, type_name):
            new_value = value
        else:
            raise TypeError(f"Invalid type  for '{attr_name}'"
                            f". Expected one of (str, {type_name}), got '{str(type(value))}'")
        setattr(self, attr_name, new_value)

    def _set_attr_with_type_cast(self, attr_name: str, value: Any, type_class: type) -> None:
        """
        Sets object attribute only if it can be converted to given type.
        """
        if type_class in {bool, int, str, float}:
            new_value = type_class(value)
        else:
            raise NotImplementedError(type_class)
        setattr(self, attr_name, new_value)

    def _set_attr_positive_int(self, attr_name: str, value: int) -> None:
        """
        Checks that value is non-negative before updating attribute
        """
        if not isinstance(value, int):
            raise TypeError(f"Invalid type for '{attr_name}'. Expected int, got '{str(type(value))}'")
        if value < 0:
            raise ValueError(f"Positive integer expected: {value}")
        setattr(self, attr_name, value)

    def _find_by_name(self, elements: list, name: str):
        """
        Iterates through list of elements and return the first whose
        name matches the name argument
        """
        for elem in elements:
            if elem.name == name:
                return elem
        return None


class Referrable(ARObject):
    """
    Group AR:REFERRABLE
    Type: Abstract
    """

    def __init__(self, name: str) -> None:
        self.name: str = name  # .SHORT-NAME
        self.parent: 'CollectableElement' = None

    @property
    def short_name(self) -> str:
        """
        Alias for .name
        """
        return self.name


class MultiLanguageReferrable(Referrable):
    """
    Group AR:MULTILANGUAGE-REFERRABLE
    Type: Abstract
    """

    def __init__(self,
                 name: str,
                 long_name: Union["MultilanguageLongName", None] = None) -> None:
        super().__init__(name)
        self.long_name: MultilanguageLongName | None = None
        if long_name is not None:
            if isinstance(long_name, MultilanguageLongName):
                self.long_name = long_name
            else:
                raise TypeError(
                    f'long_name: Expected type "MultilanguageLongName", got "{str(type(long_name))}"')


class Identifiable(MultiLanguageReferrable):
    """
    Complex-type AR:IDENTIFIABLE
    Type: Abstract
    """

    def __init__(self,
                 name: str,
                 desc: Union["MultiLanguageOverviewParagraph", tuple, str, None] = None,
                 category: str | None = None,
                 uuid: str | None = None,
                 **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.desc: MultiLanguageOverviewParagraph | None = None
        self.category = None
        self.admin_data = None
        self.introduction = None
        self.annotations = None
        self.uuid = None
        if desc is not None:
            if isinstance(desc, MultiLanguageOverviewParagraph):
                self.desc = desc
            elif isinstance(desc, str):
                self.desc = MultiLanguageOverviewParagraph.make(ar_enum.Language.FOR_ALL, desc)
            elif isinstance(desc, tuple) and len(desc) == 2:
                self.desc = MultiLanguageOverviewParagraph.make(*desc)
            else:
                raise TypeError(f"Invalid type for argument 'desc': {str(type(desc))}")
        self._assign_optional('category', category, str)
        self._assign_optional('uuid', uuid, str)


class CollectableElement(Identifiable):
    """
    AR:COLLECTABLE-ELEMENT

    Meta-class that identify either an
    AR:PACKAGE or AR-ELEMENT.
    Both types can be places inside another
    package.

    Type Abstract
    """


class ARElement(CollectableElement):
    """
    AR:AR-ELEMENT

    Base class for all package-elements

    Type: Abstract
    """

# AdminData


class AdminData(ARObject):
    """
    Complex-type AR:ADMIN-DATA
    Type: Concrete
    Tag variants: 'ADMIN-DATA'
    """

    def __init__(self, data: dict | None = None) -> None:
        self.data = data

# Reference classes


class BaseRef(ARObject, abc.ABC):
    """
    Bas type for all references
    Complex-type AR:REF
    Type: Abstract
    """

    def __init__(self,
                 value: str,
                 dest: ar_enum.IdentifiableSubTypes) -> None:
        self.value = value
        self.dest: ar_enum.IdentifiableSubTypes = None
        if dest in self._accepted_subtypes():
            self.dest = dest
        else:
            raise ValueError(f"{str(dest)} is not a valid sub-type for {str(type(self))}")

    @abc.abstractmethod
    def _accepted_subtypes(self) -> set[ar_enum.IdentifiableSubTypes]:
        """
        Subset of ar_enum.IdentifiableSubTypes defining
        which enum values are acceptable for dest
        """

    def __str__(self) -> str:
        """Returns reference as string"""
        return self.value


class CompuMethodRef(BaseRef):
    """
    CompuMethod reference
    """

    def __init__(self, value: str) -> None:
        super().__init__(value, ar_enum.IdentifiableSubTypes.COMPU_METHOD)

    def _accepted_subtypes(self) -> set[ar_enum.IdentifiableSubTypes]:
        """Acceptable values for dest"""
        return {ar_enum.IdentifiableSubTypes.COMPU_METHOD}


class FunctionPtrSignatureRef(BaseRef):
    """
    Function pointer signature reference
    """

    def __init__(self, value: str) -> None:
        super().__init__(value, ar_enum.IdentifiableSubTypes.BSW_MODULE_ENTRY)

    def _accepted_subtypes(self) -> set[ar_enum.IdentifiableSubTypes]:
        """Acceptable values for dest"""
        return {ar_enum.IdentifiableSubTypes.BSW_MODULE_ENTRY}


class ImplementationDataTypeRef(BaseRef):
    """
    ImplementationDataType reference
    """

    def __init__(self, value: str) -> None:
        super().__init__(value, ar_enum.IdentifiableSubTypes.IMPLEMENTATION_DATA_TYPE)

    def _accepted_subtypes(self) -> set[ar_enum.IdentifiableSubTypes]:
        """Acceptable values for dest"""
        return {ar_enum.IdentifiableSubTypes.IMPLEMENTATION_DATA_TYPE}


class SwAddrMethodRef(BaseRef):
    """
    SwAddrMethod reference
    """

    def __init__(self, value: str) -> None:
        super().__init__(value, ar_enum.IdentifiableSubTypes.SW_ADDR_METHOD)

    def _accepted_subtypes(self) -> set[ar_enum.IdentifiableSubTypes]:
        """Acceptable values for dest"""
        return {ar_enum.IdentifiableSubTypes.SW_ADDR_METHOD}


class SwBaseTypeRef(BaseRef):
    """
    SwBaseType reference
    """

    def __init__(self, value: str) -> None:
        super().__init__(value, ar_enum.IdentifiableSubTypes.SW_BASE_TYPE)

    def _accepted_subtypes(self) -> set[ar_enum.IdentifiableSubTypes]:
        """Acceptable values for dest"""
        return {ar_enum.IdentifiableSubTypes.SW_BASE_TYPE}


class DataConstraintRef(BaseRef):
    """
    DataConstraint reference
    """

    def __init__(self, value: str) -> None:
        super().__init__(value, ar_enum.IdentifiableSubTypes.DATA_CONSTR)

    def _accepted_subtypes(self) -> set[ar_enum.IdentifiableSubTypes]:
        """Acceptable values for dest"""
        return {ar_enum.IdentifiableSubTypes.DATA_CONSTR}


class PhysicalDimensionRef(BaseRef):
    """
    PhysicalDimension reference
    """

    def __init__(self, value: str) -> None:
        super().__init__(value, ar_enum.IdentifiableSubTypes.PHYSICAL_DIMENSION)

    def _accepted_subtypes(self) -> set[ar_enum.IdentifiableSubTypes]:
        """Acceptable values for dest"""
        return {ar_enum.IdentifiableSubTypes.PHYSICAL_DIMENSION}


class UnitRef(BaseRef):
    """
    DataConstraint reference
    """

    def __init__(self, value: str) -> None:
        super().__init__(value, ar_enum.IdentifiableSubTypes.UNIT)

    def _accepted_subtypes(self) -> set[ar_enum.IdentifiableSubTypes]:
        """Acceptable values for dest"""
        return {ar_enum.IdentifiableSubTypes.UNIT}


class IndexDataTypeRef(BaseRef):
    """
    IndexDataType reference
    """

    def __init__(self, value: str) -> None:
        super().__init__(value, ar_enum.IdentifiableSubTypes.APPLICATION_PRIMITIVE_DATA_TYPE)

    def _accepted_subtypes(self) -> set[ar_enum.IdentifiableSubTypes]:
        """Acceptable values for dest"""
        return {ar_enum.IdentifiableSubTypes.APPLICATION_PRIMITIVE_DATA_TYPE}


class ApplicationDataTypeRef(BaseRef):
    """
    Application data type reference
    """

    def _accepted_subtypes(self) -> set[ar_enum.IdentifiableSubTypes]:
        """Acceptable values for dest"""
        return {ar_enum.IdentifiableSubTypes.APPLICATION_ARRAY_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.APPLICATION_ASSOC_MAP_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.APPLICATION_COMPOSITE_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.APPLICATION_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.APPLICATION_DEFERRED_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.APPLICATION_PRIMITIVE_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.APPLICATION_RECORD_DATA_TYPE}


class AutosarDataTypeRef(BaseRef):
    """
    References to elements in AR:AUTOSAR-DATA-TYPE--SUBTYPES-ENUM
    """

    def _accepted_subtypes(self) -> set[ar_enum.IdentifiableSubTypes]:
        """Acceptable values for dest"""
        return {ar_enum.IdentifiableSubTypes.ABSTRACT_IMPLEMENTATION_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.APPLICATION_ARRAY_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.APPLICATION_ASSOC_MAP_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.APPLICATION_COMPOSITE_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.APPLICATION_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.APPLICATION_DEFERRED_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.APPLICATION_PRIMITIVE_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.APPLICATION_RECORD_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.AUTOSAR_DATA_TYPE,
                ar_enum.IdentifiableSubTypes.IMPLEMENTATION_DATA_TYPE}


class ConstantRef(BaseRef):
    """
    Reference to ConstantSpecification
    """

    def __init__(self, value: str) -> None:
        super().__init__(value, ar_enum.IdentifiableSubTypes.CONSTANT_SPECIFICATION)

    def _accepted_subtypes(self) -> set[ar_enum.IdentifiableSubTypes]:
        """Acceptable values for dest"""
        return {ar_enum.IdentifiableSubTypes.CONSTANT_SPECIFICATION}

# Documentation Elements


class Break(ARObject):
    """
    Complex-type AR:BR
    Type: Concrete
    Tag variants: BR

    Same function as the html element.

    """


class EmphasisText(ARObject):
    """
    Complex-type AR:EMPHASIS-TEXT
    Type: Concrete
    Tag variants: E

    Emphasized text

    Limitations: No support for child-elements. Type for argument elements must be string.

    """

    def __init__(self,
                 elements: None | list | str = None,
                 color: str = None,
                 font: ar_enum.EmphasisFont = None,
                 type: ar_enum.EmphasisType = None) -> None:  # pylint: disable=redefined-builtin
        self.elements = []
        self.color = color  # Attribute @COLOR
        self.font = font  # Attribute @FONT
        self.type = type  # Attribute @TYPE
        if elements is not None:
            if isinstance(elements, str):
                self.elements.append(elements)
            else:
                raise NotImplementedError("List of elements not yet supported")


class IndexEntry(ARObject):
    """
    Complex-type AR:INDEX-ENTRY
    Type: Concrete
    Tag variants: IE

    Index Entry

    Limitations: Doesn't support sub-elements as seen in XML schema.
    """

    def __init__(self, text: str) -> None:
        self.text = text  # Text content


class TechnicalTerm(ARObject):
    """
    Complex-type AR:TT
    Type: Concrete
    Tag variants: TT

    Technical Term

    """

    def __init__(self,
                 text: str,
                 tex_render: str = None,
                 type: str = None) -> None:  # pylint: disable=redefined-builtin
        self.tex_render = tex_render  # attribute @TEX-RENDER
        self.type = type  # attribute @TYPE
        self.text = text  # Text content


class Subscript(ARObject):
    """
    Complex-type AR:SUPSCRIPT
    Type: Concrete
    Tag variants: SUB

    Subscript is based on the same Complex-type

    """

    def __init__(self, text: str) -> None:
        self.text = text  # Simple content


class Superscript(ARObject):
    """
    Complex-type AR:SUPSCRIPT
    Type: Concrete
    Tag variants: SUP

    Superscript
    """

    def __init__(self, text: str) -> None:
        self.text = text  # Simple content

    def __str__(self) -> str:
        """
        Convert to basic string
        """
        return "^" + self.text


class LanguageSpecific(ARObject):
    """
    Complex-type AR:LANGUAGE-SPECIFIC
    Type: Abstract
    """

    def __init__(self, language: ar_enum.Language) -> None:
        assert isinstance(language, ar_enum.Language)
        self.language = language  # Attribute @L


class MixedContentForLongName(LanguageSpecific):
    """
    Group AR:MIXED-CONTENT-FOR-LONG-NAME
    Type: Abstract
    """

    def __init__(self, language: ar_enum.Language) -> None:
        super().__init__(language)
        self.parts = []  # Unbounded list of str | TT | E | SUP | SUB | IE

    def append(self, part: str | TechnicalTerm | EmphasisText | Subscript | Subscript):
        """
        Checks type validity before adding element to elements
        """
        if isinstance(part, (str, TechnicalTerm, EmphasisText, Subscript, Subscript, IndexEntry)):
            self.parts.append(part)
        else:
            raise TypeError('Unsupported element type: ' + str(type(part)))


class MixedContentForOverviewParagraph(LanguageSpecific):
    """
    Group AR:MIXED-CONTENT-FOR-OVERVIEW-PARAGRAPH
    Type: Abstract
    """

    def __init__(self, language: ar_enum.Language) -> None:
        super().__init__(language)
        self.parts = []  # Unbounded list of str | TT | E | SUP | SUB | IE
        # Unsupported elements:
        # FT : AR:SL-OVERVIEW-PARAGRAPH
        # TRACE-REF: Complex-type
        # XREF: AR:-XREF-TARGET

    def append(self, part: str | TechnicalTerm | EmphasisText | Subscript | Subscript):
        """
        Checks type validity before adding element to elements
        """
        if isinstance(part, (str, TechnicalTerm, EmphasisText, Subscript, Subscript, IndexEntry)):
            self.parts.append(part)
        else:
            raise TypeError('Unsupported element type: ' + str(type(part)))


class LanguageLongName(MixedContentForLongName):
    """
    Complex-type AR:L-LONG-NAME
    Type: Concrete
    Tag: L-4

    Longname for a specific language.

    The parts parameter can be a single string or a list of mixed types.

    Accepted mixed types:
    * strings
    * TechnicalTerm
    * EmphasisText
    * Subscript
    * Subscript
    """

    def __init__(self, language: ar_enum.Language, parts: None | str | list[Any] = None) -> None:
        super().__init__(language)
        if parts is not None:
            if isinstance(parts, str):
                self.append(parts)
            else:
                for part in parts:
                    self.append(part)


class MultilanguageLongName(ARObject):
    """
    Complex-type AR:MULTILANGUAGE-LONG-NAME
    Type: Concrete
    Tag variants: 'LABEL' | 'LONG-NAME'
    """

    def __init__(self,
                 long_name: None | tuple[ar_enum.Language,
                                         str] | LanguageLongName = None) -> None:
        self.elements: list[LanguageLongName] = []
        if long_name is not None:
            if isinstance(long_name, LanguageLongName):
                self.append(long_name)
            elif isinstance(long_name, tuple):
                self.append(LanguageLongName(long_name[0], long_name[1]))
            else:
                raise TypeError('Invalid type for long_name. '
                                f'Expected tuple[ar_enum.Language,str] or LanguageLongName,'
                                f' got "{str(type(long_name))}"')

    def append(self, long_name: LanguageLongName) -> None:
        """
        Adds long_name to its inner list with type-check
        """
        assert isinstance(long_name, LanguageLongName)
        self.elements.append(long_name)


class LanguageOverviewParagraph(MixedContentForOverviewParagraph):
    """
    Complex-type AR:L-OVERVIEW-PARAGRAPH
    Type: Concrete
    Tag variants: 'L-2'

    Overview paragraph for specific language

    The parts parameter can be a single string or a list of mixed types.

    Accepted mixed types:
    * strings
    * TechnicalTerm
    * EmphasisText
    * Subscript
    * Subscript
    """

    def __init__(self, language: ar_enum.Language, parts: None | str | list[Any] = None) -> None:
        super().__init__(language)
        if parts is not None:
            if isinstance(parts, str):
                self.append(parts)
            else:
                for part in parts:
                    self.append(part)


class MultiLanguageOverviewParagraph(ARObject):
    """
    Complex-type AR:MULTI-LANGUAGE-OVERVIEW-PARAGRAPH
    Type: Concrete
    Tag variants: 'DESC' | 'ITEM-LABEL' | 'CHANGE' | 'REASON'
    """

    def __init__(self,
                 paragraph: None | tuple[ar_enum.Language,
                                         str] | LanguageOverviewParagraph = None) -> None:
        self.elements: list[LanguageOverviewParagraph] = []
        if paragraph is not None:
            if isinstance(paragraph, LanguageOverviewParagraph):
                self.append(paragraph)
            elif isinstance(paragraph, tuple) and len(paragraph) == 2:
                self.append(LanguageOverviewParagraph(*paragraph))
            else:
                raise TypeError('Invalid type for paragraph. '
                                f'Expected tuple[ar_enum.Language,str] or LanguageOverviewParagraph,'
                                f' got "{str(type(paragraph))}"')

    def append(self, paragraph: LanguageOverviewParagraph) -> None:
        """
        Adds long_name to its inner list with type-check
        """
        assert isinstance(paragraph, LanguageOverviewParagraph)
        self.elements.append(paragraph)

    @classmethod
    def make(cls, language: ar_enum.Language, paragraph: str):
        """
        Convenience method for creating instances from text string
        """
        return cls(LanguageOverviewParagraph(language, paragraph))


class DocumentViewSelectable(ARObject):
    """
    Group AR:DOCUMENT-VIEW-SELECTABLE
    Type: Abstract

    Experiment with named attributes for this class while keeping
    Unknown parent attributes hidden in kwargs

    """

    def __init__(self,
                 semantic_information: None | str = None,
                 view: None | str = None) -> None:
        self.semantic_information = semantic_information  # Attribute 'SI'
        self.view = view  # Attribute 'VIEW'
        if semantic_information is not None and (not isinstance(semantic_information, str)):
            raise TypeError(
                f"semantic_information: Expected type 'str', got '{str(type(semantic_information))}'")
        if view is not None and (not isinstance(view, str)):
            raise TypeError(
                f"view: Expected type 'str', got '{str(type(view))}'")


class Paginateable(DocumentViewSelectable):
    """
    Group AR:PAGINATEABLE
    Type: Abstract

    Experiment with named attributes for this class while keeping
    Unknown parent attributes hidden in kwargs
    """

    def __init__(self,
                 page_break: None | ar_enum.PageBreak = None,
                 keep_with_previous: None | ar_enum.KeepWithPrevious = None,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.page_break = page_break  # Attribute 'BREAK'
        self.keep_with_previous = keep_with_previous  # Attribute 'KEEP-WITH-PREVIOUS'
        if (page_break is not None) and (not isinstance(page_break, ar_enum.PageBreak)):
            raise TypeError(
                f"page_break: Expected type 'PageBreak', got '{str(type(page_break))}'")
        if (keep_with_previous is not None) and (not isinstance(keep_with_previous, ar_enum.KeepWithPrevious)):
            raise TypeError(
                f"page_break: Expected type 'PageBreak', got '{str(type(keep_with_previous))}'")


class MixedContentForParagraph(LanguageSpecific):
    """
    Group AR:MIXED-CONTENT-FOR-PARAGRAPH
    Type: Abstract
    """

    def __init__(self, language: ar_enum.Language) -> None:
        super().__init__(language)
        self.parts = []  # Unbounded list of str | BR | E | IE | SUB | SUP | TT
        # Unsupported elements:
        # FT : AR:SL-OVERVIEW-PARAGRAPH
        # STD: AR:STD
        # TRACE-REF : Specialization of AR:REF
        # XDOC: AR:XDOC
        # XFILE: AR:XFILE
        # XREF: AR:XREF
        # XREF-TARGET: AR:-XREF-TARGET

    def append(self,
               part: str | Break | EmphasisText | IndexEntry | Subscript | Subscript | TechnicalTerm):
        """
        Checks type validity before adding element to elements
        """
        if isinstance(part, (str, Break, EmphasisText, IndexEntry, Subscript, Subscript, TechnicalTerm)):
            self.parts.append(part)
        else:
            raise TypeError('Unsupported element type: ' + str(type(part)))


class LanguageParagraph(MixedContentForParagraph):
    """
    Complex-type AR:L-PARAGRAPH
    Type: Concrete
    Tag variants: 'L-1'

    Paragraph for specific language

    The parts parameter can be a single string or a list of mixed types.

    Accepted mixed types:
    * strings
    * Break
    * EmphasisText
    * TechnicalTerm
    * Subscript
    * Subscript
    """

    def __init__(self, language: ar_enum.Language, parts: None | str | list[Any] = None) -> None:
        super().__init__(language)
        if parts is not None:
            if isinstance(parts, str):
                self.append(parts)
            else:
                for part in parts:
                    self.append(part)


class MultiLanguageParagraph(Paginateable):
    """
    Complex-type AR:MULTI-LANGUAGE-PARAGRAPH
    Type: Concrete
    Tag variants: 'P'
    """

    def __init__(self,
                 paragraph: None | tuple[ar_enum.Language,
                                         str] | LanguageParagraph = None,
                 help_entry: None | str = None,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.help_entry = help_entry  # Attribute 'HELP-ENTRY'
        self.elements: list[LanguageParagraph] = []
        if paragraph is not None:
            if isinstance(paragraph, LanguageParagraph):
                self.append(paragraph)
            elif isinstance(paragraph, tuple):
                self.append(LanguageParagraph(paragraph[0], paragraph[1]))
            else:
                raise TypeError('Invalid type for paragraph. '
                                f'Expected tuple[ar_enum.Language,str] or LanguageParagraph,'
                                f' got "{str(type(paragraph))}"')

    def append(self, paragraph: LanguageParagraph) -> None:
        """
        Adds long_name to its inner list with type-check
        """
        assert isinstance(paragraph, LanguageParagraph)
        self.elements.append(paragraph)


class MixedContentForVerbatim(LanguageSpecific):
    """
    Group AR:MIXED-CONTENT-FOR-VERBATIM
    Type: Abstract

    This includes AR:WHITESPACE-CONTROLLED as it
    does not have any attributes or elements of its
    own.
    """

    def __init__(self, language: ar_enum.Language) -> None:
        super().__init__(language)
        self.parts = []  # Unbounded list of str | BR | E | TT
        # Unsupported elements:
        # XREF: AR:XREF

    def append(self,
               part: str | Break | EmphasisText | TechnicalTerm):
        """
        Checks type validity before adding element to elements
        """
        if isinstance(part, (str, Break, EmphasisText, TechnicalTerm)):
            self.parts.append(part)
        else:
            raise TypeError('Unsupported element type: ' + str(type(part)))


class LanguageVerbatim(MixedContentForVerbatim):
    """
    Complex-type AR:L-VERBATIM
    Type: Concrete
    Tag variants: 'L-5'
    """

    def __init__(self, language: ar_enum.Language, parts: None | str | list[Any] = None) -> None:
        super().__init__(language)
        if parts is not None:
            if isinstance(parts, str):
                self.append(parts)
            else:
                for part in parts:
                    self.append(part)


class MultiLanguageVerbatim(Paginateable):
    """
    Complex-type AR:MULTI-LANGUAGE-VERBATIM
    Type: Concrete
    Tag variants: 'VERBATIM'
    """

    def __init__(self,
                 element: None | tuple[ar_enum.Language,
                                       str] | LanguageVerbatim = None,
                 allow_break: None | str = None,
                 float: None | ar_enum.Float = None,  # pylint: disable=redefined-builtin
                 page_wide: None | ar_enum.PageWide = None,
                 help_entry: None | str = None,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.allow_break = allow_break  # Attribute 'ALLOW-BREAK'
        self.float = float  # Attribte 'FLOAT'
        self.page_wide = page_wide  # Attribute 'PGWIDE'
        self.help_entry = help_entry  # Attribute 'HELP-ENTRY'
        self.elements: list[LanguageVerbatim] = []
        if element is not None:
            if isinstance(element, LanguageVerbatim):
                self.append(element)
            elif isinstance(element, tuple):
                self.append(LanguageVerbatim(element[0], element[1]))
            else:
                raise TypeError('Invalid type for element. '
                                f'Expected tuple[ar_enum.Language,str] or LanguageVerbatim,'
                                f' got "{str(type(element))}"')

    def append(self, paragraph: LanguageVerbatim) -> None:
        """
        Adds long_name to its inner list with type-check
        """
        assert isinstance(paragraph, LanguageVerbatim)
        self.elements.append(paragraph)


class MixedContentForUnitNames(ARObject):
    """
    Group MIXED-CONTENT-FOR-UNIT-NAMES
    Type: Abstract
    """

    def __init__(self) -> None:
        self.parts = []  # Unbounded list of str | SUB | SUP

    def append(self,
               part: str | Break | EmphasisText | TechnicalTerm):
        """
        Checks type validity before adding element to elements
        """
        if isinstance(part, (str, Subscript, Superscript)):
            self.parts.append(part)
        else:
            raise TypeError('Unsupported element type: ' + str(type(part)))


class SingleLanguageUnitNames(MixedContentForUnitNames):
    """
    Complex type AR:SINGLE-LANGUAGE-UNIT-NAMES
    Type: Concrete
    Tag variants: 'PRM-UNIT' | 'UNIT-DISPLAY-NAME' | 'UNIT-DISPLAY-NAME' | 'DISPLAY-NAME'
    """

    def __init__(self, parts: str | list | None = None) -> None:
        super().__init__()
        if parts is not None:
            if isinstance(parts, Iterable):
                for part in parts:
                    self.append(part)
            else:
                self.append(parts)

    def __str__(self) -> str:
        """
        Convert to string if the unit name has simple
        type (at most one part of type str).
        """
        result = []
        for part in self.parts:
            if isinstance(part, str):
                result.append(part)
            elif isinstance(part, Superscript):
                result.append(str(part))
            else:
                raise ValueError("Unable to convert to string from multiple parts")
        return "".join(result)


class DocumentationBlock(ARObject):
    """
    Complex type AR:DOCUMENTATION-BLOCK
    Type: Concrete
    Tag Variants: 'INTRODUCTION', 'DEF', 'VALUE', 'ANNOTATION-TEXT', 'REMARK'
                  'COND', 'DESCRICPTION', 'RATIONALE', 'DEPENDENCIES', 'USE-CASE',
                  'CONFLICTS', 'SUPPORTING-MATERIAL', 'SW-GENERIC-AXIS-DESC'
    """

    def __init__(self,
                 element: MultiLanguageParagraph | MultiLanguageVerbatim | list[Any] | None = None) -> None:
        self.elements: list[MultiLanguageParagraph | MultiLanguageVerbatim] = []
        if element is not None:
            if isinstance(element, Iterable):
                for elem in element:
                    self.append(elem)
            else:
                self.append(element)

    def append(self, element: MultiLanguageParagraph | MultiLanguageVerbatim) -> None:
        """
        Appends new element with type check
        """
        assert isinstance(element,
                          (MultiLanguageParagraph,
                           MultiLanguageVerbatim))
        self.elements.append(element)


class GeneralAnnotation(ARObject):
    """
    Group AR:GENERAL-ANNOTATION
    Type: Abstract
    """

    def __init__(self,
                 label: MultilanguageLongName | None = None,
                 origin: str | None = None,
                 text: DocumentationBlock | None = None) -> None:
        super().__init__()
        self.label = label  # .LABEL
        self.origin = origin  # .ANNOTATION-ORIGIN
        self.text = text  # .ANNOTATION-TEXT


class Annotation(GeneralAnnotation):
    """
    Complex-type AR:ANNOTATION
    Type: Concrete
    """

    def __init__(self,  # pylint: disable=useless-parent-delegation
                 label: MultilanguageLongName | None = None,
                 origin: str | None = None,
                 text: DocumentationBlock | None = None) -> None:
        super().__init__(label, origin, text)


# ComputationMethods

class CompuRational(ARObject):
    """
    AR:COMPU-RATIONAL-COEFFS
    Type: Concrete
    Tag variants: 'COMPU-RATIONAL-COEFFS'
    """

    def __init__(self,
                 numerator: tuple[int | float] | list[int | float] | None,
                 denominator: tuple[int | float] | list[int | float] | None = None) -> None:
        if numerator is not None:
            if not isinstance(numerator, (tuple, list)):
                raise TypeError("Parameter for 'numerator' must be either a list or a tuple")
            self.numerator = tuple(numerator)
        else:
            self.numerator = None
        if denominator is not None:
            if not isinstance(denominator, (tuple, list)):
                raise TypeError("Parameter for 'denominator' must be either a list or a tuple")
            self.denominator = tuple(denominator)
        else:
            self.denominator = None


class CompuConst(ARObject):
    """
    AR:COMPU-CONST
    Type: Concrete

    Handles AR:COMPU-CONST-NUMERIC-CONTENT
    and AR:COMPU-CONST-TEXT-CONTENT dynamically
    """

    def __init__(self, value: int | float | str):
        self.value = value


class CompuScale(ARObject):
    """
    AR:COMPU-SCALE
    Type: Concrete
    Tag variants: 'COMPU-SCALE'
    """

    def __init__(self,
                 content: CompuConst | CompuRational | None = None,
                 lower_limit: int | float | str | None = None,
                 upper_limit: int | float | str | None = None,
                 label: str | None = None,
                 symbol: str | None = None,
                 desc: MultiLanguageOverviewParagraph | None = None,
                 mask: int | None = None,
                 inverse_value: CompuConst | None = None,
                 lower_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED,
                 upper_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED) -> None:
        self.content = content                      # CHOICE(COMPU-SCALE-CONSTANT-CONTENTS, COMPU-SCALE-RATIONAL-FORMULA) # noqa E501 pylint: disable=C0301
        self.lower_limit = lower_limit              # .LOWER-LIMIT
        self.upper_limit = upper_limit              # .UPPER-LIMIT
        self.label = label                          # .SHORT-LABEL
        self.symbol = symbol                        # .SYMBOL
        self.desc = desc                            # .DESC
        self.mask = mask                            # .MASK
        self.inverse_value: CompuConst | None = None  # .COMPU-INVERSE-VALUE
        if inverse_value is not None:
            if isinstance(inverse_value, CompuConst):
                self.inverse_value = inverse_value
            elif isinstance(inverse_value, (int, float, str)):
                self.inverse_value = CompuConst(inverse_value)
            else:
                raise TypeError(f"Invalid type for 'inverse_value': {str(type(inverse_value))}")
        self.lower_limit_type = lower_limit_type    # .LOWER-LIMIT@INTERVAL-TYPE
        self.upper_limit_type = upper_limit_type    # .UPPER-LIMIT@INTERVAL-TYPE
        # .VARIATION-POINT not supported

    @property
    def content_type(self) -> ar_enum.CompuScaleContent:
        """
        What kind of content does this CompuScale have?
        """
        if isinstance(self.content, CompuConst):
            return ar_enum.CompuScaleContent.CONSTANT
        elif isinstance(self.content, CompuRational):
            return ar_enum.CompuScaleContent.RATIONAL
        else:
            return ar_enum.CompuScaleContent.NONE


class Computation(ARObject):
    """
    AR:COMPU
    Type: Concrete
    Tag variants: 'COMPU-INTERNAL-TO-PHYS' | 'COMPU-PHYS-TO-INTERNAL'
    """

    def __init__(self,
                 compu_scales: list[CompuScale] | None = None,
                 default_value: CompuConst | int | float | str | None = None) -> None:

        self.compu_scales = compu_scales
        self.default_value: CompuConst | int | float | str | None = None  # .COMPU-DEFAULT-VALUE
        if isinstance(default_value, CompuConst):
            self.default_value = default_value
        elif isinstance(default_value, (int, float, str)):
            self.default_value = CompuConst(default_value)

    @classmethod
    def make_value_table(cls: "Computation",
                         elements: list[Any],
                         default_value: CompuConst | int | float | str | None = None,
                         auto_label: bool = True):
        """
        Creates new const-based computation from values in list

        When elements is a list of strings:
            Creates one CompuScale per list item and automatically calculates lower and upper limits

        When elements is a list of tuples:
            If 2-tuple: First element is both lower_limit and upper_limit, second element is text value.
            If 3-tuple: First element is lower_limit, second element is upper_limit, third element is text value.

        auto_label: automatically creates a <SHORT-LABEL> based on the text value.

        """
        compu_scales = []
        for i, elem in enumerate(elements):
            label = None
            if isinstance(elem, str):
                lower_limit, upper_limit, value = i, i, elem
            elif isinstance(elem, tuple):
                if len(elem) == 2:
                    lower_limit, upper_limit, value = (elem[0], elem[0], elem[1])
                elif len(elem) == 3:
                    lower_limit, upper_limit, value = elem
                else:
                    raise ValueError(f"Invalid length of tuple: {len(elem)}")
            else:
                raise TypeError(f"Invalid type of element: {str(type(elem))}")
            if auto_label and isinstance(value, str):
                label = value
            compu_scales.append(CompuScale(CompuConst(value), lower_limit, upper_limit, label))
        return cls(compu_scales, default_value)

    @classmethod
    def make_rational(cls: "Computation",
                      scaling_factor: int | float = 1,
                      offset: int | float = 0,
                      lower_limit: int | float | str | None = None,
                      upper_limit: int | float | str | None = None,
                      default_value: CompuConst | int | float | str | None = None,
                      lower_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED,
                      upper_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED) -> None:
        """
        Creates a new Computation instance with one COMPU-SCALE containing numerator
        and denominator.

        """
        numerator = [offset, float(scaling_factor)]
        denominator = [1]
        compu_scales = [CompuScale(CompuRational(numerator, denominator),
                                   lower_limit,
                                   upper_limit,
                                   lower_limit_type=lower_limit_type,
                                   upper_limit_type=upper_limit_type)]
        return cls(compu_scales, default_value)


class CompuMethod(ARElement):
    """
    AR:COMPU-METHOD
    Type: Concrete
    Tag Variants: 'COMPU-METHOD'
    """

    def __init__(self, name: str,
                 int_to_phys: Computation | None = None,
                 phys_to_int: Computation | None = None,
                 unit_ref: UnitRef | None = None,
                 display_format: str | None = None,
                 **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.int_to_phys = int_to_phys        # .COMPU-INTERNAL-TO-PHYS
        self.phys_to_int = phys_to_int        # .COMPU-PHYS-TO-INTERNAL
        self.unit_ref = unit_ref              # .UNIT-REF
        self.display_format = display_format  # .DISPLAY-FORMAT

    def ref(self) -> CompuMethodRef | None:
        """
        Reference
        """
        if self.parent is None:
            return None
        ref_parts: list[str] = [self.name]
        self.parent.update_ref_parts(ref_parts)
        value = '/'.join(reversed(ref_parts))
        return CompuMethodRef(value)


# Constraint elements


class LimitObject(ARObject):
    """
    Base class for elements that has
    upper and lower limits
    Type: Abstract
    """

    def __init__(self,
                 lower_limit: int | float | None = None,
                 upper_limit: int | float | None = None,
                 lower_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED,
                 upper_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED) -> None:

        self.lower_limit = lower_limit              # .LOWER-LIMIT
        self.upper_limit = upper_limit              # .UPPER-LIMIT
        self.lower_limit_type = lower_limit_type    # .LOWER-LIMIT@INTERVAL-TYPE
        self.upper_limit_type = upper_limit_type    # .UPPER-LIMIT@INTERVAL-TYPE

    @property
    def is_empty(self) -> bool:
        """Overrides is_empty from base class"""
        return self.is_empty_with_ignore({"lower_limit_type", "upper_limit_type"})

    def check_value(self, value: int | float) -> bool:
        """
        Checks if given value is inside the constraint limits
        """
        if self.lower_limit_type == ar_enum.IntervalType.CLOSED:
            if value < self.lower_limit:
                return False
        elif value <= self.lower_limit:
            return False
        if self.upper_limit_type == ar_enum.IntervalType.CLOSED:
            if value > self.upper_limit:
                return False
        elif value >= self.upper_limit:
            return False
        return True


class ScaleConstraint(LimitObject):
    """
    AR:SCALE-CONSTR
    Type: Concrete
    Tag variants: 'SCALE-CONSTR'
    """

    def __init__(self,
                 label: str | None = None,
                 desc: MultiLanguageOverviewParagraph | None = None,
                 lower_limit: int | float | None = None,
                 upper_limit: int | float | None = None,
                 validity: ar_enum.ScaleConstraintValidity | None = None,
                 lower_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED,
                 upper_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED) -> None:
        super().__init__(lower_limit, upper_limit, lower_limit_type, upper_limit_type)
        self.label = label
        self.desc = desc
        self.validity = validity


class ConstraintBase(LimitObject):
    """
    Base class data constraint rules
    Type: Abstract
    """

    def __init__(self,
                 lower_limit: int | float | None = None,
                 upper_limit: int | float | None = None,
                 scale_constrs: list[ScaleConstraint] | None = None,
                 max_gradient: int | float | None = None,
                 max_diff: int | float | None = None,
                 monotony: ar_enum.Monotony | None = None,
                 lower_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED,
                 upper_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED) -> None:
        super().__init__(lower_limit, upper_limit, lower_limit_type, upper_limit_type)
        self.scale_constrs = list(scale_constrs) if scale_constrs else []
        self.max_gradient = max_gradient
        self.max_diff = max_diff
        self.monotony = monotony


class InternalConstraint(ConstraintBase):
    """
    AR:INTERNAL-CONSTRS
    Type: Concrete
    Tag variants: 'INTERNAL-CONSTRS'
    """

    def __init__(self,
                 lower_limit: int | float | None = None,
                 upper_limit: int | float | None = None,
                 scale_constr: list[ScaleConstraint] | None = None,
                 max_gradient: int | float | None = None,
                 max_diff: int | float | None = None,
                 monotony: ar_enum.Monotony | None = None,
                 lower_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED,
                 upper_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED) -> None:
        super().__init__(lower_limit,
                         upper_limit,
                         scale_constr,
                         max_gradient,
                         max_diff,
                         monotony,
                         lower_limit_type,
                         upper_limit_type)


class PhysicalConstraint(ConstraintBase):
    """
    AR:PHYS-CONSTRS
    Type: Concrete
    Tag variants: 'PHYS-CONSTRS'
    """

    def __init__(self,
                 lower_limit: int | float | None = None,
                 upper_limit: int | float | None = None,
                 scale_constr: list[ScaleConstraint] | None = None,
                 max_gradient: int | float | None = None,
                 max_diff: int | float | None = None,
                 monotony: ar_enum.Monotony | None = None,
                 unit_ref: UnitRef | None = None,
                 lower_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED,
                 upper_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED) -> None:
        super().__init__(lower_limit,
                         upper_limit,
                         scale_constr,
                         max_gradient,
                         max_diff,
                         monotony,
                         lower_limit_type,
                         upper_limit_type)
        self.unit_ref = unit_ref


class DataConstraintRule(ARObject):
    """
    AR:DATA-CONSTR-RULE
    Type: Concrete
    Tag variants: 'DATA-CONSTR-RULE'
    """

    def __init__(self,
                 internal: InternalConstraint | None = None,
                 physical: PhysicalConstraint | None = None,
                 level: int | None = None) -> None:
        self.internal = internal   # .INTERNAL-CONSTRS
        self.physical = physical   # .PHYS-CONSTRS
        self.level = level         # .CONSTR-LEVEL


class DataConstraint(ARElement):
    """
    AR:DATA-CONSTR
    Type: Concrete
    Tag variants: 'DATA-CONSTR'
    """

    def __init__(self, name: str,
                 rules: list[DataConstraintRule] | None = None,
                 **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.rules = []
        if rules is not None:
            for rule in rules:
                assert isinstance(rule, DataConstraintRule)
            self.rules.extend(rules)

    def ref(self) -> DataConstraintRef:
        """
        Reference
        """
        assert self.parent is not None
        ref_parts: list[str] = [self.name]
        self.parent.update_ref_parts(ref_parts)
        value = '/'.join(reversed(ref_parts))
        return DataConstraintRef(value)

    @classmethod
    def make_physical(cls: "DataConstraint",
                      name: str,
                      lower_limit: int | float | None = None,
                      upper_limit: int | float | None = None,
                      scale_constr: list[ScaleConstraint] | None = None,
                      max_gradient: int | float | None = None,
                      max_diff: int | float | None = None,
                      monotony: ar_enum.Monotony | None = None,
                      unit_ref: UnitRef | None = None,
                      lower_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED,
                      upper_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED,
                      **kwargs) -> "DataConstraint":
        """
        Convenience method for creating a DataConstraint
        that contains a single physical constraint.
        """
        rule = DataConstraintRule(physical=PhysicalConstraint(lower_limit,
                                                              upper_limit,
                                                              scale_constr,
                                                              max_gradient,
                                                              max_diff,
                                                              monotony,
                                                              unit_ref,
                                                              lower_limit_type,
                                                              upper_limit_type))
        return cls(name, [rule], **kwargs)

    @classmethod
    def make_internal(cls: "DataConstraint",
                      name: str,
                      lower_limit: int | float | None = None,
                      upper_limit: int | float | None = None,
                      scale_constr: list[ScaleConstraint] | None = None,
                      max_gradient: int | float | None = None,
                      max_diff: int | float | None = None,
                      monotony: ar_enum.Monotony | None = None,
                      lower_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED,
                      upper_limit_type: ar_enum.IntervalType = ar_enum.IntervalType.CLOSED,
                      **kwargs) -> "DataConstraint":
        """
        Convenience method for creating a DataConstraint
        that contains a single internal constraint.
        """
        rule = DataConstraintRule(internal=InternalConstraint(lower_limit,
                                                              upper_limit,
                                                              scale_constr,
                                                              max_gradient,
                                                              max_diff,
                                                              monotony,
                                                              lower_limit_type,
                                                              upper_limit_type))
        return cls(name, [rule], **kwargs)

# Unit elements


class Unit(ARElement):
    """
    Complex type AR:UNIT
    Type: Concrete
    Tag variants: 'UNIT'
    """

    def __init__(self, name: str,
                 display_name: str | SingleLanguageUnitNames | None = None,
                 factor: float | None = None,
                 offset: float | None = None,
                 physical_dimension_ref: str | PhysicalDimensionRef | None = None,
                 **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.display_name: SingleLanguageUnitNames | None = None  # .DISPLAY-NAME
        self.physical_dimension_ref: PhysicalDimensionRef | None = None  # .PHYSICAL-DIMENSION-REF
        self.factor: float | None = None  # .FACTOR-SI-TO-UNIT
        self.offset: float | None = None  # .OFFSET-SI-TO-UNIT
        if display_name is not None:
            if isinstance(display_name, str):
                self.display_name = SingleLanguageUnitNames(display_name)
            elif isinstance(display_name, SingleLanguageUnitNames):
                self.display_name = display_name
            else:
                raise TypeError(f"display_name: Invalid type '{str(type(display_name))}'")
        if physical_dimension_ref is not None:
            if isinstance(physical_dimension_ref, str):
                self.physical_dimension_ref = PhysicalDimensionRef(display_name)
            elif isinstance(physical_dimension_ref, PhysicalDimensionRef):
                self.physical_dimension_ref = physical_dimension_ref
            else:
                raise TypeError(f"physical_dimension_ref: Invalid type '{str(type(physical_dimension_ref))}'")
        self._assign_optional('factor', factor, float)
        self._assign_optional('offset', offset, float)


# DataDictionary and DataType elements


class BaseType(ARElement):
    """
    Merge of Complex-types AR:BASE-TYPE, AR:BASE-TYPE-DEFINITION,
    AR:BASE-TYPE-DIRECT-DEFINITION
    Type: Abstract
    """

    def __init__(self, name: str, **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.size: int | None = None  # .BASE-TYPE-SIZE
        self.max_size: int | None = None  # .MAX-BASE-TYPE-SIZE
        self.encoding: str | None = None  # .BASE-TYPE-ENCODING
        self.alignment: int | None = None  # .MEM-ALIGNMENT
        self.byte_order: ar_enum.ByteOrder | None = None  # .BYTE-ORDER
        self.native_declaration: str | None = None  # .NATIVE-DECLARATION


class SwBaseType(BaseType):
    """
    Complex-type AR:SW-BASE-TYPE
    Type: Concrete
    Tag variants: SW-BASE-TYPE
    """

    def __init__(self,
                 name: str,
                 size: int | None = None,
                 max_size: int | None = None,
                 encoding: str | None = None,
                 alignment: int | None = None,
                 byte_order: ar_enum.ByteOrder | None = None,
                 native_declaration: str | None = None,
                 **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.size = size
        self.max_size = max_size
        self.encoding = encoding
        self.alignment = alignment
        self.byte_order = byte_order
        self.native_declaration = native_declaration

    def ref(self) -> SwBaseTypeRef | None:
        """
        Reference
        """
        if self.parent is None:
            return None
        ref_parts: list[str] = [self.name]
        self.parent.update_ref_parts(ref_parts)
        value = '/'.join(reversed(ref_parts))
        return SwBaseTypeRef(value)


class SwBitRepresentation(ARObject):
    """
    SW-BIT-REPRESENTATION
    Type: Concrete
    """

    def __init__(self,
                 position: int | None = None,
                 num_bits: int | None = None) -> None:
        super().__init__()
        self.position: int | None = None
        self.num_bits: int | None = None
        self._assign_optional('position', position, int)
        self._assign_optional('num_bits', num_bits, int)


class SwTextProps(ARObject):
    """
    Complex type AR:SW-TEXT-PROPS
    Type: Concrete
    Tag Variants: 'SW-TEXT-PROPS'
    """

    def __init__(self,
                 array_size_semantics: ar_enum.ArraySizeSemantics | None = None,
                 max_text_size: int | None = None,
                 base_type_ref: SwBaseTypeRef | str | None = None,
                 fill_char: int | None = None,
                 ):
        self.array_size_semantics: ar_enum.ArraySizeSemantics | None = None   # .ARRAY-SIZE-SEMANTICS
        self.max_text_size: int | None = None                                 # .SW-MAX-TEXT-SIZE
        self.base_type_ref: SwBaseTypeRef | str | None = None                 # .BASE-TYPE-REF
        self.fill_char: int | None = None                                     # .FILL-CHAR
        self._assign_optional('array_size_semantics', array_size_semantics, ar_enum.ArraySizeSemantics)
        self._assign_optional('max_text_size', max_text_size, int)
        self._assign_optional('base_type_ref', base_type_ref, SwBaseTypeRef)
        self._assign_optional('fill_char', fill_char, int)


class SwPointerTargetProps(ARObject):
    """
    Complex type AR:SW-POINTER-TARGET-PROPS
    Type: Concrete
    Tag Variants: 'SW-POINTER-TARGET-PROPS'
    """

    def __init__(self,
                 target_category: str | None = None,
                 sw_data_def_props: Union["SwDataDefProps", "SwDataDefPropsConditional", None] = None,
                 function_ptr_signature_ref: FunctionPtrSignatureRef | None = None
                 ) -> None:
        self.target_category: str | None = None  # .TARGET-CATEGORY
        self.sw_data_def_props: Union["SwDataDefProps", None] = None  # .SW-DATA-DEF-PROPS
        self.function_ptr_signature_ref: FunctionPtrSignatureRef | None = None  # .FUNCTION-POINTER-SIGNATURE-REF
        self._assign_optional("target_category", target_category, str)
        self._assign_optional("function_ptr_signature_ref", function_ptr_signature_ref, FunctionPtrSignatureRef)
        if sw_data_def_props is not None:
            if isinstance(sw_data_def_props, SwDataDefProps):
                self.sw_data_def_props = sw_data_def_props
            elif isinstance(sw_data_def_props, SwDataDefPropsConditional):
                self.sw_data_def_props = SwDataDefProps(sw_data_def_props)
            else:
                raise TypeError("'sw_data_def_props' must be one of (SwDataDefProps, SwDataDefPropsConditional)")


class SwDataDefPropsConditional(ARObject):
    """
    Merge of Complex-types AR:SW-DATA-DEF-PROPS-CONDITIONAL and
    AR:SW-DATA-DEF-PROPS-CONTENT
    Type: Concrete
    Tag Variants: SW-DATA-DEF-PROPS-CONDITIONAL
    """

    def __init__(self,
                 display_presentation: ar_enum.DisplayPresentation | None = None,
                 step_size: float | None = None,
                 annotations: Annotation | list[Annotation] | None = None,
                 sw_addr_method_ref: str | SwAddrMethodRef | None = None,
                 base_type_ref: SwBaseTypeRef | None = None,
                 compu_method_ref: str | CompuMethodRef | None = None,
                 data_constraint_ref: str | DataConstraintRef | None = None,
                 impl_data_type_ref: str | ImplementationDataTypeRef | None = None,
                 unit_ref: str | UnitRef | None = None,
                 alignment: int | float | None = None,
                 bit_representation: SwBitRepresentation | None = None,
                 calibration_access: ar_enum.SwCalibrationAccess | None = None,
                 text_props: SwTextProps | None = None,
                 display_format: str | None = None,
                 impl_policy: ar_enum.SwImplPolicy | None = None,
                 additional_native_type_qualifier: str | None = None,
                 intended_resolution: int | float | None = None,
                 interpolation_method: str | None = None,
                 is_virtual: bool | None = None,
                 ptr_target_props: SwPointerTargetProps | None = None
                 ) -> None:
        # .DISPLAY-PRESENTATION
        self.display_presentation: ar_enum.DisplayPresentation | None = None
        self.step_size: float | None = None  # .STEP-SIZE : AR:FLOAT
        # .SW-VALUE-BLOCK-SIZE-MULTS not supported.
        self.annotations: list[Annotation] = []  # .ANNOTATIONS
        self.sw_addr_method_ref: SwAddrMethodRef | None = None  # .SW-ADDR-METHOD-REF
        self.alignment: int | str | None = None  # .SW-ALIGNMENT
        self.base_type_ref: SwBaseTypeRef | None = None  # .BASE-TYPE-REF
        self.bit_representation: SwBitRepresentation | None = None  # .SW-BIT-REPRESENTATION
        self.calibration_access: ar_enum.SwCalibrationAccess | None = None  # .SW-CALIBRATION-ACCESS
        # .SW-VALUE-BLOCK-SIZE not supported.
        # .SW-CALPRM-AXIS-SET not yet supported. Low on priority list.
        self.text_props: SwTextProps | None = None  # .SW-TEXT-PROPS
        # .SW-COMPARISON-VARIABLES not yet supported. Low on priority list.
        self.compu_method_ref: CompuMethodRef | None = None
        self.data_constraint_ref: DataConstraintRef | None = None
        # .SW-DATA-DEPENDENCY not yet supported. Low on priority list.
        self.display_format: str | None = None  # .DISPLAY-FORMAT
        self.impl_data_type_ref: ImplementationDataTypeRef | None = None  # .IMPLEMENTATION-DATA-TYPE-REF
        # .SW-HOST-VARIABLE not yet supported. Low on priority list.
        self.impl_policy: ar_enum.SwImplPolicy | None = None  # .SW-IMPL-POLICY
        self.additional_native_type_qualifier: str | None = None  # .ADDITIONAL-NATIVE-TYPE-QUALIFIER
        self.intended_resolution: int | float | None = None  # .SW-INTENDED-RESOLUTION
        self.interpolation_method: str | None = None  # .SW-INTERPOLATION-METHOD
        # .INVALID-VALUE not yet supported.
        # .MC-FUNCTION not yet supported. Low on priority list.
        self.is_virtual: bool | None = None  # .IS-VIRTUAL
        self.ptr_target_props: SwPointerTargetProps | None = None  # .SW-POINTER-TARGET-PROPS
        # .SW-RECORD-LAYOUT-REF not yet supported. Low on priority list.
        # .SW-REFRESH-TIMING not yet supported. Low on priority list.
        self.unit_ref = None  # .UNIT-REF
        # .VALUE-AXIS-DATA-TYPE-REF not yet supported. Low on priority list.

        self._assign_optional('display_presentation', display_presentation, ar_enum.DisplayPresentation)
        self._assign_optional('step_size', step_size, float)
        if annotations is not None:
            if isinstance(annotations, Annotation):
                self.annotations.append(annotations)
            elif isinstance(annotations, Iterable):
                for annotation in annotations:
                    if not isinstance(annotation, Annotation):
                        raise TypeError(
                            f"Param annotations: Expected type 'Annotation', got '{str(type(annotation))}'")
                    self.annotations.append(annotation)
            else:
                raise TypeError(
                    "Param annotations: "
                    f"Expected type 'Annotation' or list[Annotation], got '{str(type(annotations))}'")
        self._assign_optional('sw_addr_method_ref', sw_addr_method_ref, SwAddrMethodRef)
        self._assign_int_or_str_pattern_optional('alignment', alignment, alignment_type_re)
        self._assign_optional('base_type_ref', base_type_ref, SwBaseTypeRef)
        if bit_representation is not None:
            if not isinstance(bit_representation, SwBitRepresentation):
                raise TypeError(f"bit_representation: Invalid type '{str(type(bit_representation))}'."
                                " Expected 'SwBitRepresentation'")
            self.bit_representation = bit_representation
        self._assign_optional('calibration_access', calibration_access, ar_enum.SwCalibrationAccess)
        if text_props is not None:
            if not isinstance(text_props, SwTextProps):
                raise TypeError(f"text_props: Invalid type '{str(type(text_props))}'."
                                " Expected 'SwTextProps'")
            self.text_props = text_props
        self._assign_optional('compu_method_ref', compu_method_ref, CompuMethodRef)
        self._assign_optional('data_constraint_ref', data_constraint_ref, DataConstraintRef)
        self._assign_optional('impl_data_type_ref', impl_data_type_ref, ImplementationDataTypeRef)
        self._assign_optional('unit_ref', unit_ref, UnitRef)
        self._assign_int_or_str_pattern_optional('display_format', display_format, display_format_str_re)
        self._assign_optional('impl_policy', impl_policy, ar_enum.SwImplPolicy)
        self._assign_optional('additional_native_type_qualifier',
                              additional_native_type_qualifier, str)
        if intended_resolution is not None:
            if isinstance(intended_resolution, (int, float)):
                self.intended_resolution = intended_resolution
            else:
                raise TypeError(f"Invalid type '{str(type(intended_resolution))}' for paramater 'intended_resolution'")
        self._assign_optional('interpolation_method', interpolation_method, str)
        self._assign_optional('is_virtual', is_virtual, bool)
        if ptr_target_props is not None:
            self._set_attr_with_strict_type('ptr_target_props', ptr_target_props, SwPointerTargetProps)


class SwDataDefProps(ARObject):
    """
    SW-DATA-DEF-PROPS
    Type: Concrete
    """

    def __init__(self, variants: SwDataDefPropsConditional | list[SwDataDefPropsConditional] | None = None) -> None:
        super().__init__()
        self.variants: list[SwDataDefPropsConditional] = []  # .SW-DATA-DEF-PROPS-VARIANTS
        if variants is not None:
            if isinstance(variants, list):
                for variant in variants:
                    self.append(variant)
            elif isinstance(variants, SwDataDefPropsConditional):
                self.append(variants)
            else:
                raise TypeError("variant must be one of (SwDataDefPropsConditional, list[SwDataDefPropsConditional])")

    def __getitem__(self, index: int) -> SwDataDefPropsConditional:
        """
        Accessor of variants list
        """
        return self.variants[index]

    def __len__(self) -> int:
        """
        Length of variants list
        """
        return len(self.variants)

    def __iter__(self):
        """
        Iterator of variants list
        """
        return iter(self.variants)

    def append(self, variant: SwDataDefPropsConditional):
        """
        Appends SW-DATA-DEF-PROPS-CONDITIONAL to variants list
        """
        if isinstance(variant, SwDataDefPropsConditional):
            self.variants.append(variant)
        else:
            raise TypeError("variant must be of type SwDataDefPropsConditional")


class AutosarDataType(ARElement):
    """
    Element AUTOSAR-DATA-TYPE
    Type: Abstract
    """

    def __init__(self,
                 name: str,
                 sw_data_def_props: SwDataDefProps | SwDataDefPropsConditional | None = None,
                 **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.sw_data_def_props: SwDataDefProps | None = None
        if sw_data_def_props is not None:
            if isinstance(sw_data_def_props, SwDataDefProps):
                self.sw_data_def_props = sw_data_def_props
            elif isinstance(sw_data_def_props, SwDataDefPropsConditional):
                self.sw_data_def_props = SwDataDefProps(sw_data_def_props)
            else:
                raise TypeError("'sw_data_def_props' must be one of (SwDataDefProps, SwDataDefPropsConditional)")


class ImplementationProps(Referrable):
    """
    Complex type AR:IMPLEMENTATION-PROPS
    Type: Abstract
    """

    def __init__(self,
                 name: str,
                 symbol: str | None = None) -> None:
        super().__init__(name)
        self.symbol: str | None = None
        self._assign_optional('symbol', symbol, str)


class SymbolProps(ImplementationProps):
    """
    Complex type AR:SYMBOL-PROPS
    Type: Concrete
    Tag Variants: 'SYMBOL-PROPS', 'EVENT-SYMBOL-PROPS'
    """


class ImplementationDataTypeElement(Identifiable):
    """
    Complex type AR:IMPLEMENTATION-DATA-TYPE-ELEMENT
    Type: Concrete
    Tag variants: 'IMPLEMENTATION-DATA-TYPE-ELEMENT'
    """

    def __init__(self,
                 name: str,
                 sw_data_def_props: SwDataDefProps | SwDataDefPropsConditional | None = None,
                 array_size: int | None = None,
                 array_impl_policy: ar_enum.ArrayImplPolicy | None = None,
                 array_size_handling: ar_enum.ArraySizeHandling | None = None,
                 array_size_semantics: ar_enum.ArraySizeSemantics | None = None,
                 sub_elements: list["ImplementationDataTypeElement"] | None = None,
                 is_optional: bool | None = None,
                 **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.array_size: int | None = None                                      # .ARRAY-SIZE
        self.array_impl_policy: ar_enum.ArrayImplPolicy | None = None           # .ARRAY-IMPL-POLICY
        self.array_size_handling: ar_enum.ArraySizeHandling | None = None       # .ARRAY-SIZE-HANDLING
        self.array_size_semantics: ar_enum.ArraySizeSemantics | None = None     # .ARRAY-SIZE-SEMANTICS
        self.is_optional: bool | None = None                                    # .IS-OPTIONAL
        self.sub_elements: list["ImplementationDataTypeElement"] | None = []    # .SUB-ELEMENTS
        self.sw_data_def_props: SwDataDefProps | None = None                    # .SW-DATA-DEF-PROPS
        self._assign_optional_positive_int("array_size", array_size)
        self._assign_optional("array_impl_policy", array_impl_policy, ar_enum.ArrayImplPolicy)
        self._assign_optional("array_size_handling", array_size_handling, ar_enum.ArraySizeHandling)
        self._assign_optional("array_size_semantics", array_size_semantics, ar_enum.ArraySizeSemantics)
        self._assign_optional("is_optional", is_optional, bool)
        if sub_elements is not None:
            for elem in sub_elements:
                self.append(elem)
        if sw_data_def_props is not None:
            if isinstance(sw_data_def_props, SwDataDefProps):
                self.sw_data_def_props = sw_data_def_props
            elif isinstance(sw_data_def_props, SwDataDefPropsConditional):
                self.sw_data_def_props = SwDataDefProps(sw_data_def_props)
            else:
                raise TypeError("'sw_data_def_props' must be one of (SwDataDefProps, SwDataDefPropsConditional)")

    def append(self, elem: "ImplementationDataTypeElement") -> None:
        """
        Appends elem to sub_element list
        """
        if isinstance(elem, ImplementationDataTypeElement):
            self.sub_elements.append(elem)
        else:
            raise TypeError("'elem' must be of type ImplementationDataTypeElement")


class ImplementationDataType(AutosarDataType):
    """
    AR: IMPLEMENTATION-DATA-TYPE
    Type: Concrete
    Tag Variants: 'IMPLEMENTATION-DATA-TYPE'
    """

    def __init__(self,
                 name: str,
                 dynamic_array_size_profile: str | None = None,
                 is_struct_with_optional_element: bool | None = None,
                 sub_elements: list[ImplementationDataTypeElement] | None = None,
                 symbol_props: SymbolProps | None = None,
                 type_emitter: str | None = None,
                 **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.dynamic_array_size_profile: str | None = None                  # .DYNAMIC-ARRAY-SIZE-PROFILE
        self.is_struct_with_optional_element: bool | None = None            # .IS-STRUCT-WITH-OPTIONAL-ELEMENT
        self.sub_elements: list[ImplementationDataTypeElement] = []         # .SUB-ELEMENTS
        self.symbol_props: SymbolProps | None = None                        # .SYMBOL-PROPS
        self.type_emitter: str | None = None                                # .TYPE-EMITTER
        self._assign_optional('dynamic_array_size_profile', dynamic_array_size_profile, str)
        self._assign_optional('is_struct_with_optional_element', is_struct_with_optional_element, bool)
        self._assign_optional('type_emitter', type_emitter, str)
        if sub_elements is not None:
            for elem in sub_elements:
                self.append(elem)
        if symbol_props is not None:
            if isinstance(symbol_props, SymbolProps):
                self.symbol_props = symbol_props
            else:
                raise TypeError("'symbol_props' must be of type SymbolProps")

    def append(self, elem: ImplementationDataTypeElement) -> None:
        """
        Appends elem to sub_element list
        """
        if isinstance(elem, ImplementationDataTypeElement):
            self.sub_elements.append(elem)
        else:
            raise TypeError("'elem' must be of type ImplementationDataTypeElement")

    def ref(self):
        """
        Returns a new reference to this object
        """
        if self.parent is None:
            return None
        ref_parts: list[str] = [self.name]
        self.parent.update_ref_parts(ref_parts)
        value = '/'.join(reversed(ref_parts))
        return ImplementationDataTypeRef(value)

    def find(self, ref: str) -> Any:
        """
        Finds item by reference
        """
        assert "/" not in ref
        return self._find_by_name(self.sub_elements, ref)


class DataPrototype(Identifiable):
    """
    AR:DATA-PROTOTYPE
    Type: Abstract
    """

    def __init__(self,
                 name: str,
                 sw_data_def_props: SwDataDefProps | SwDataDefPropsConditional | None = None,
                 **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.sw_data_def_props: SwDataDefProps | None = None  # .SW-DATA-DEF-PROPS
        if sw_data_def_props is not None:
            if isinstance(sw_data_def_props, SwDataDefProps):
                self.sw_data_def_props = sw_data_def_props
            elif isinstance(sw_data_def_props, SwDataDefPropsConditional):
                self.sw_data_def_props = SwDataDefProps(sw_data_def_props)
            else:
                raise TypeError("'sw_data_def_props' must be one of (SwDataDefProps, SwDataDefPropsConditional)")


class AutosarDataPrototype(DataPrototype):
    """
    AR:AUTOSAR-DATA-PROTOTYPE
    Type: Abstract
    """

    def __init__(self,
                 name: str,
                 type_ref: AutosarDataTypeRef | None = None,
                 **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.type_ref: AutosarDataTypeRef | None = None  # .TYPE-TREF
        self._assign_optional_strict("type_ref", type_ref, AutosarDataTypeRef)


class VariableDataPrototype(AutosarDataPrototype):
    """
    AR:VARIABLE-DATA-PROTOTYPE
    Type: Concrete
    """

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, kwargs)
        self.init_value = None  # .INIT-VALUE
        # .VARIATION-POINT not supported


class ApplicationDataType(AutosarDataType):
    """
    Group AR:APPLICATION-DATA-TYPE
    Type: Abstract
    """


class ApplicationCompositeDataType(ApplicationDataType):
    """
    Group AR:APPLICATION-COMPOSITE-DATA-TYPE
    Type: Abstract
    """

    @property
    def is_composite(self):
        """Is this a composite data type?"""
        return True


class ApplicationPrimitiveDataType(ApplicationDataType):
    """
    Complex type AR:APPLICATION-PRIMITIVE-DATA-TYPE
    Type Concrete
    Tag variants: 'APPLICATION-PRIMITIVE-DATA-TYPE'
    """

    @property
    def is_composite(self):
        """Is this a composite data type?"""
        return False

    def ref(self) -> ApplicationDataTypeRef:
        """
        Reference
        """
        if self.parent is None:
            return None
        ref_parts: list[str] = [self.name]
        self.parent.update_ref_parts(ref_parts)
        value = '/'.join(reversed(ref_parts))
        return ApplicationDataTypeRef(value, ar_enum.IdentifiableSubTypes.APPLICATION_PRIMITIVE_DATA_TYPE)


class ApplicationCompositeElementDataPrototype(DataPrototype):
    """
    AR:APPLICATION-COMPOSITE-ELEMENT-DATA-PROTOTYPE
    Type: Abstract
    """

    def __init__(self,
                 name: str,
                 type_ref: ApplicationDataTypeRef | None = None,
                 **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.type_ref: ApplicationDataTypeRef | None = None  # .TYPE-TREF
        self._assign_optional_strict('type_ref', type_ref, ApplicationDataTypeRef)


class ApplicationArrayElement(ApplicationCompositeElementDataPrototype):
    """
    Complex type AR:APPLICATION-ARRAY-ELEMENT
    Type: Concrete
    Tag variants: 'ELEMENT'
    """

    def __init__(self,
                 name: str,
                 max_number_of_elements: int | None = None,
                 array_size_handling: ar_enum.ArraySizeHandling | None = None,
                 array_size_semantics: ar_enum.ArraySizeSemantics | None = None,
                 index_data_type_ref: IndexDataTypeRef | None = None,
                 **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.array_size_handling: ar_enum.ArraySizeHandling | None = None     # .ARRAY-SIZE-HANDLING
        self.array_size_semantics: ar_enum.ArraySizeSemantics | None = None   # .ARRAY-SIZE-SEMANTICS
        self.max_number_of_elements: int | None = None                        # ."MAX-NUMBER-OF-ELEMENTS
        self.index_data_type_ref: IndexDataTypeRef | None = None              # .INDEX-DATA-TYPE-REF
        self._assign_optional("array_size_handling", array_size_handling, ar_enum.ArraySizeHandling)
        self._assign_optional("array_size_semantics", array_size_semantics, ar_enum.ArraySizeSemantics)
        self._assign_optional_positive_int("max_number_of_elements", max_number_of_elements)
        self._assign_optional("index_data_type_ref", index_data_type_ref, IndexDataTypeRef)


class ApplicationArrayDataType(ApplicationCompositeDataType):
    """
    Complex type AR:APPLICATION-ARRAY-DATA-TYPE
    Type: Concrete
    Tag variants: 'APPLICATION-ARRAY-DATA-TYPE'
    """

    def __init__(self,
                 name: str,
                 dynamic_array_size_profile: str | None = None,
                 element: ApplicationArrayElement | None = None,
                 **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.dynamic_array_size_profile: str | None = None                  # .DYNAMIC-ARRAY-SIZE-PROFILE
        self.element: ApplicationArrayElement | None = None                 # .ELEMENT
        self._assign_optional('dynamic_array_size_profile', dynamic_array_size_profile, str)
        self._assign_optional_strict('element', element, ApplicationArrayElement)

    def ref(self) -> ApplicationDataTypeRef | None:
        """
        Reference
        """
        if self.parent is None:
            return None
        ref_parts: list[str] = [self.name]
        self.parent.update_ref_parts(ref_parts)
        value = '/'.join(reversed(ref_parts))
        return ApplicationDataTypeRef(value, ar_enum.IdentifiableSubTypes.APPLICATION_ARRAY_DATA_TYPE)


class ApplicationRecordElement(ApplicationCompositeElementDataPrototype):
    """
    Complex type AR:APPLICATION-RECORD-ELEMENT
    Type: Concrete
    Tag variants: 'APPLICATION-RECORD-ELEMENT'
    """

    def __init__(self,
                 name: str,
                 is_optional: bool | None = None,
                 **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.is_optional: bool | None = None                  # .IS-OPTIONAL
        self._assign_optional('is_optional', is_optional, bool)


class ApplicationRecordDataType(ApplicationCompositeDataType):
    """
    Complex type AR:APPLICATION-RECORD-DATA-TYPE
    Type: Concrete
    Tag variants: 'APPLICATION-RECORD-DATA-TYPE'
    """

    def __init__(self,
                 name: str,
                 elements: ApplicationRecordElement | list[ApplicationRecordElement] | None = None,
                 **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.elements: list[ApplicationRecordElement] = []
        if elements is not None:
            if isinstance(elements, ApplicationRecordElement):
                self.append(elements)
            elif isinstance(elements, list):
                self.extend(elements)

    def append(self, element: ApplicationRecordElement) -> None:
        """
        Appends element to elements list
        """
        if isinstance(element, ApplicationRecordElement):
            self.elements.append(element)
        else:
            raise TypeError("'element' must be of type ApplicationRecordElement")

    def extend(self, elements: list[ApplicationRecordElement]) -> None:
        """
        Extends elements to elements list
        """
        for element in elements:  # We want to type-check each element before adding to internal list
            self.append(element)

    def ref(self) -> ApplicationDataTypeRef | None:
        """
        Reference
        """
        if self.parent is None:
            return None
        ref_parts: list[str] = [self.name]
        self.parent.update_ref_parts(ref_parts)
        value = '/'.join(reversed(ref_parts))
        return ApplicationDataTypeRef(value, ar_enum.IdentifiableSubTypes.APPLICATION_RECORD_DATA_TYPE)


class DataTypeMap(ARObject):
    """
    AR:DATA-TYPE-MAP
    Type: Concrete
    Tag variants: 'DATA-TYPE-MAP'
    """

    def __init__(self,
                 appl_data_type_ref: ApplicationDataTypeRef | None = None,
                 impl_data_type_ref: ImplementationDataTypeRef | None = None,
                 ) -> None:
        self.appl_data_type_ref = appl_data_type_ref   # .APPLICATION-DATA-TYPE-REF
        self.impl_data_type_ref = impl_data_type_ref   # .IMPLEMENTATION-DATA-TYPE-REF


class DataTypeMappingSet(ARElement):
    """
    AR:DATA-TYPE-MAPPING-SET
    Type: Concrete
    Tag variants: 'DATA-TYPE-MAPPING-SET'
    """

    def __init__(self,
                 name: str,
                 data_type_maps: DataTypeMap | list[DataTypeMap] | None = None,
                 **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.data_type_maps: list[DataTypeMap] = []  # .DATA-TYPE-MAPS
        self.mode_request_type_maps = []  # .MODE-REQUEST-TYPE-MAPS (Not yet implemented)
        if data_type_maps is not None:
            if isinstance(data_type_maps, DataTypeMap):
                self.append(data_type_maps)
            elif isinstance(data_type_maps, list):
                for data_type_map in data_type_maps:
                    self.append(data_type_map)
            else:
                raise TypeError(f'data_type_maps: Invalid type "{str(type(data_type_maps))}"')

    def append(self, element: DataTypeMap) -> None:
        """
        Appends element to one of the inner lists based on parameter type
        Currently, appending to mode_request_type_maps isn't
        implemented.
        """
        if isinstance(element, DataTypeMap):
            self.data_type_maps.append(element)
        else:
            raise TypeError(f'Unexpected type: "{str(type(element))}"')


class ValueList(ARObject):
    """
    Complex-type AR:VALUE-LIST
    Type: Concrete
    Tag variants: 'SW-ARRAYSIZE'
    """

    def __init__(self, values: list[int | float | NumericalValue] | None = None) -> None:
        self.values = []
        if values is not None:
            if isinstance(values, (int, float)):
                self.append(values)
            else:
                for value in values:
                    self.append(value)

    def append(self, value: int | float | NumericalValue) -> None:
        """
        Adds value to list of values
        """
        if isinstance(value, (int, float, NumericalValue)):
            self.values.append(value)
        else:
            raise TypeError(f"Invalid type for value: {str(type(value))}")


# Software address method (partly implemented)


class SwAddrMethod(ARElement):
    """
    Complex-type AR:SW-ADDR-METHOD
    Type: Concrete
    Tag Variants: 'SW-ADDR-METHOD'
    """

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.memory_allocation_keyword_policy = None  # .MEMORY-ALLOCATION-KEYWORD-POLICY
        self.options = []  # .OPTIONS
        self.section_initialization_policy = None  # .SECTION-INITIALIZATION-POLICY
        self.section_type = None  # .SECTION-TYPE

    def ref(self) -> SwAddrMethodRef:
        """
        Reference
        """
        assert self.parent is not None
        ref_parts: list[str] = [self.name]
        self.parent.update_ref_parts(ref_parts)
        value = '/'.join(reversed(ref_parts))
        return SwAddrMethodRef(value)

# Calibration data


SwValueElement = Union[int, float, str, NumericalValue, "ValueGroup"]  # Type alias


class SwValues(ARObject):
    """
    Complex-type AR:SW-VALUES
    Type: Concrete
    Tag variants: SW-VALUES-PHYS
    """

    def __init__(self,
                 values: list[SwValueElement] | None = None) -> None:
        self.values = []
        if values is not None:
            if isinstance(values, (int, float, str, NumericalValue, ValueGroup)):
                self.append(values)
            elif isinstance(values, list):
                for value in values:
                    self.append(value)

    def append(self, value: SwValueElement) -> None:
        """
        Appends value to list of values
        XML elements not supported:

        - VTF
        - VF
        """
        if isinstance(value, (int, float, str, NumericalValue, ValueGroup)):
            self.values.append(value)
        else:
            raise TypeError(f"Invalid value type: {str(type(value))}")


class ValueGroup(SwValues):
    """
    Complex-type AR:VALUE-GROUP
    Type: Concrete
    Tag variants: VG
    """

    def __init__(self,
                 label: str | MultilanguageLongName | tuple[ar_enum.Language, str] | LanguageLongName | None = None,
                 values: SwValues | None = None) -> None:
        self.label: MultilanguageLongName | None = None
        super().__init__(values)
        if label is not None:
            if isinstance(label, MultilanguageLongName):
                self.label = label
            elif isinstance(label, (tuple, LanguageLongName)):
                self.label = MultilanguageLongName(label)
            else:
                raise TypeError(f"Invalid type for 'label': {str(type(label))}")


class SwAxisCont(ARObject):
    """
    Complex-type AR:SW-AXIS-CONT
    Type: Concrete
    Tag variants: SW-AXIS-CONT
    """

    def __init__(self,
                 category: ar_enum.CalibrationAxisCategory | None = None,
                 unit_ref: UnitRef | None = None,
                 unit_display_name: SingleLanguageUnitNames | None = None,
                 sw_axis_index: int | str | None = None,
                 sw_array_size: ValueList | None = None,
                 sw_values_phys: SwValues | None = None) -> None:
        self.category: ar_enum.CalibrationAxisCategory = None  # .CATEGORY
        self.unit_ref: UnitRef = None  # .UNIT-REF
        self.unit_display_name: SingleLanguageUnitNames = None  # .UNIT-DISPLAY_NAME
        self.sw_axis_index: int | str = None  # .SW-AXIS-INDEX
        self.sw_array_size: ValueList = None  # .SW-ARRAYSIZE
        self.sw_values_phys: SwValues = None  # .SW-VALUES-PHYS
        self._assign_optional('category', category, ar_enum.CalibrationAxisCategory)
        self._assign_optional_strict('unit_ref', unit_ref, UnitRef)
        self._assign_optional_strict('unit_display_name', unit_display_name, SingleLanguageUnitNames)
        if sw_axis_index is not None:
            if isinstance(sw_axis_index, (int, str)):
                self.sw_axis_index = sw_axis_index
            else:
                error_msg = "Invalid type for parameter 'sw_axis_index'. Expected 'int' or 'str', "
                raise TypeError(error_msg + f"got '{str(type(sw_axis_index))}'")
        self._assign_optional_strict('sw_array_size', sw_array_size, ValueList)
        self._assign_optional_strict('sw_values_phys', sw_values_phys, SwValues)


class SwValueCont(ARObject):
    """
    Complex-type AR:SW-VALUE-CONT
    Type: Concrete
    Tag variants: SW-VALUE-CONT
    """

    def __init__(self,
                 unit_ref: UnitRef | None = None,
                 unit_display_name: SingleLanguageUnitNames | None = None,
                 sw_array_size: ValueList | None = None,
                 sw_values_phys: SwValues | None = None) -> None:
        self.unit_ref: UnitRef = None  # .UNIT-REF
        self.unit_display_name: SingleLanguageUnitNames = None  # .UNIT-DISPLAY_NAME
        self.sw_array_size: ValueList = None  # .SW-ARRAYSIZE
        self.sw_values_phys: SwValues = None  # .SW-VALUES-PHYS
        self._assign_optional_strict('unit_ref', unit_ref, UnitRef)
        self._assign_optional_strict('unit_display_name', unit_display_name, SingleLanguageUnitNames)
        self._assign_optional_strict('sw_array_size', sw_array_size, ValueList)
        self._assign_optional_strict('sw_values_phys', sw_values_phys, SwValues)


# Constant and value specifications


class ValueSpecification(ARObject):
    """
    Group AR:VALUE-SPECIFCATION
    Type: Abstract
    Base class for value specifications
    """

    def __init__(self, label: str | None = None) -> None:
        self.label = label  # .SHORT-LABEL
        # .VARIATION-POINT not supported

    @classmethod
    def make_value(cls, data: Any) -> ValueSpeficationElement:
        """
        Builds value specification based on Python data
        """
        label = None
        default_pattern = None
        if isinstance(data, tuple):
            if not isinstance(data[0], str):
                raise TypeError("First tuple element must be a string")
            if len(data) == 2:
                label, value = data
            elif len(data) == 3:
                label, value, default_pattern = data
            else:
                raise ValueError(f"Too many elements in tuple: {repr(data)}")
        else:
            value = data
        return ValueSpecification._make_from_args(label, value, default_pattern)

    @classmethod
    def _make_from_args(cls, label: str | None,
                        value: Any,
                        default_pattern: int | None = None) -> ValueSpeficationElement:
        if isinstance(value, (int, float)):
            return NumericalValueSpecification(label, value)
        elif isinstance(value, str):
            return TextValueSpecification(label, value)
        elif value is None:
            return NotAvailableValueSpecification(label, default_pattern)
        elif isinstance(value, list):
            if not isinstance(value[0], str):
                raise TypeError("First element of a list must be a string")
            if value[0].upper() in ("A", "ARRAY"):
                return ValueSpecification._make_array_value_spefication(label, value[1:])
            elif value[0].upper() in ("R", "RECORD"):
                return ValueSpecification._make_record_value_spefication(label, value[1:])
            else:
                raise ValueError(f"Invalid element type: {str(type(value[0]))}")
        else:
            raise TypeError(f"Invalid value type: {str(type(value))}")

    @classmethod
    def _make_array_value_spefication(cls, label: str | None, values: list) -> "ArrayValueSpecification":
        elements = []
        for value in values:
            elements.append(ValueSpecification.make_value(value))
        return ArrayValueSpecification(label, elements)

    @classmethod
    def _make_record_value_spefication(cls, label: str | None, values: list) -> "RecordValueSpecification":
        fields = []
        for value in values:
            fields.append(ValueSpecification.make_value(value))
        return RecordValueSpecification(label, fields)


class TextValueSpecification(ValueSpecification):
    """
    Complex-type AR:TEXT-VALUE-SPECIFICATION
    Type: Concrete
    Tag variants: 'TEXT-VALUE-SPECIFICATION'
    """

    def __init__(self, label: str | None = None, value: str | None = None) -> None:
        super().__init__(label)
        self.value = None if value is None else str(value)


class NumericalValueSpecification(ValueSpecification):
    """
    Complex-type AR:NUMERICAL-VALUE-SPECIFICATION
    Type: Concrete
    Tag variants: 'NUMERICAL-VALUE-SPECIFICATION'
    """

    def __init__(self, label: str | None = None, value: int | float | None = None) -> None:
        super().__init__(label)
        self.value = value


class NotAvailableValueSpecification(ValueSpecification):
    """
    Complex-type AR:NOT-AVAILABLE-VALUE-SPECIFICATION
    Type: Concrete
    Tag variants: 'NOT-AVAILABLE-VALUE-SPECIFICATION'
    """

    def __init__(self,
                 label: str | None = None,
                 default_pattern: int | None = None,
                 default_pattern_format: ar_enum.ValueFormat = ar_enum.ValueFormat.DEFAULT
                 ) -> None:
        super().__init__(label)
        if isinstance(default_pattern, int) and default_pattern < 0:
            raise ValueError("default_pattern must be a positive integer")
        self.default_pattern = default_pattern
        self.default_pattern_format = default_pattern_format  # Currently not used


class ArrayValueSpecification(ValueSpecification):
    """
    Complex-type AR:ARRAY-VALUE-SPECIFICATION
    Type: Concrete
    Tag variants: 'ARRAY-VALUE-SPECIFICATION'
    """

    def __init__(self,
                 label: str | None = None,
                 elements: list[ValueSpeficationElement] | None = None
                 ) -> None:
        super().__init__(label)
        self.elements: list[ValueSpeficationElement] = []
        if elements is not None:
            if isinstance(elements, ValueSpecification):
                self.append(elements)
            elif isinstance(elements, list):
                for element in elements:
                    self.append(element)

    def append(self, element: ValueSpeficationElement):
        """
        Appends element to array specification
        """
        if not isinstance(element, ValueSpecification):
            raise TypeError(f"Invalid type for 'element': {str(type(element))}")
        self.elements.append(element)


class RecordValueSpecification(ValueSpecification):
    """
    Complex-type AR:RECORD-VALUE-SPECIFICATION
    Type: Concrete
    Tag variants: 'RECORD-VALUE-SPECIFICATION'
    """

    def __init__(self,
                 label: str | None = None,
                 fields: list[ValueSpeficationElement] | None = None
                 ) -> None:
        super().__init__(label)
        self.fields: list[ValueSpeficationElement] = []
        if fields is not None:
            if isinstance(fields, ValueSpecification):
                self.append(fields)
            elif isinstance(fields, list):
                for field in fields:
                    self.append(field)

    def append(self, field: ValueSpeficationElement):
        """
        Appends field to record specification
        """
        if not isinstance(field, ValueSpecification):
            raise TypeError(f"Invalid type for 'field': {str(type(field))}")
        self.fields.append(field)


class ApplicationValueSpecification(ValueSpecification):
    """
    Complex-type AR:APPLICATION-VALUE-SPECIFICATION
    Type: Concrete
    Tag variants: APPLICATION-VALUE-SPECIFICATION
    """

    def __init__(self,
                 label: str | None = None,
                 category: str | None = None,
                 sw_axis_conts: SwAxisCont | list[SwAxisCont] | None = None,
                 sw_value_cont: SwValueCont | None = None
                 ) -> None:
        super().__init__(label)
        self.category: str = None
        self.sw_axis_conts: list[SwAxisCont] = []
        self.sw_value_cont: SwValueCont = None
        self._assign_optional_strict("category", category, str)
        self._assign_optional_strict("sw_value_cont", sw_value_cont, SwValueCont)
        if sw_axis_conts is not None:
            if isinstance(sw_axis_conts, SwAxisCont):
                self.sw_axis_conts.append(sw_axis_conts)
            elif isinstance(sw_axis_conts, list):
                for elem in sw_axis_conts:
                    if isinstance(elem, SwAxisCont):
                        self.sw_axis_conts.append(elem)
                    else:
                        error_msg = "sw_axis_conts: Elements in list must of type SwAxisCont."
                        raise TypeError(error_msg + f" Got {str(type(elem))}")
            else:
                error_msg = "sw_axis_conts: argument must be either SwAxisCont or list[SwAxisCont]."
                raise TypeError(error_msg + f" Got {str(type(sw_axis_conts))}")


class ConstantSpecification(ARElement):
    """
    Complex-type AR:CONSTANT-SPECIFICATION
    Type: Concrete
    Tag Variants: 'CONSTANT-SPECIFICATION'
    """

    def __init__(self, name: str, value: ValueSpeficationElement | None = None, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.value: ValueSpeficationElement = None  # .VALUE-SPEC
        if value is not None:
            if isinstance(value, ValueSpecification):
                self.value = value
            else:
                error_msg = "Invalid type for parameter 'value'. Expected a subclass of ValueSpecification,"
                raise TypeError(error_msg + f" got {str(type(value))}")

    def ref(self) -> ConstantRef:
        """
        Reference
        """
        assert self.parent is not None
        ref_parts: list[str] = [self.name]
        self.parent.update_ref_parts(ref_parts)
        value = '/'.join(reversed(ref_parts))
        return ConstantRef(value)

    @classmethod
    def make_constant(cls,
                      name: str,
                      value: tuple[str, Any] | Any,
                      **kwargs) -> "ConstantSpecification":
        """
        Creates a new constant object and populates it from Python data.
        """
        value = ValueSpecification.make_value(value)
        return cls(name, value, **kwargs)


class ConstantReference(ValueSpecification):
    """
    Complex type AR:CONSTANT-REFERENCE
    Type: Concrete
    Tag variants 'CONSTANT-REFERENCE'

    It's easy to confuse this with the ConstantRef class.
    This class is just a wrapper around an instance of ConstantRef.
    """

    def __init__(self,
                 label: str | None = None,
                 constant_ref: ConstantRef | None = None) -> None:
        self.constant_ref: ConstantRef = None
        super().__init__(label)
        self._assign_optional_strict("constant_ref", constant_ref, ConstantRef)

# !!UNFINISHED!! Port Interfaces


class PortInterface(ARElement):
    """
    Implements AR:PORT-INTERFACE
    Type: Abstract
    """

    def __init__(self, name: str, **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.is_service: None | bool = None
        self.namespaces = None
        self.service_kind: None | ar_enum.ServiceKind = None


class DataInterface(PortInterface):
    """
    AR-DATA-INTERFACE
    IsAbstract: True

    Base class for data-concerned interfaces (as opposed to operations-based)
    """


class SenderReceiverInterface(DataInterface):
    """
    AR-SENDER-RECEIVER-INTERFACE
    Type: Concrete

    Base class for data-concerned interfaces (as opposed to operations-based)
    """

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.data_elements = []  # .DATA-ELEMENTS
        self.invalidation_policies = None  # .INVALIDATION-POLICYS
        # .META-DATA-ITEM-SETS not supported

# !!UNFINISHED!! Component Types


class SoftwareComponentType(ARElement):
    """
    Implements AR:SW-COMPONENT-TYPE
    Type: Abstract
    """

    def __init__(self, name: str, kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.documentations = None  # AR:SW-COMPONENT-DOCUMENTATIONS
        self.consistency_needs = None  # AR:CONSISTENCY-NEEDSS
        self.ports = None  # AR:PORTS
        self.port_groups = None  # AR:PORT_GROUPS
        self.swc_mapping_constraint_refs = None  # AR:SWC-MAPPING-CONSTRAINT-REFS
        self.unit_group_refs = None  # AR:UNIT-GROUP-REFS


class AtomicSoftwareComponentType(SoftwareComponentType):
    """
    Implements AR:ATOMIC-SW-COMPONENT-TYPE
    Type: Abstract
    """

    def __init__(self, name: str, kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.internal_behaviors = None  # AR:INTERNAL-BEHAVIORS
        self.symbol_props = None  # AR:SYMBOL-PROPS


class ApplicationSoftwareComponentType(AtomicSoftwareComponentType):
    """
    Implements AR:APPLICATION-SW-COMPONENT-TYPE
    Type: Concrete
    """

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, kwargs)

# Package (Partly implemented)


class Package(CollectableElement):
    """
    AR:PACKAGE
    """

    def __init__(self, name: str, **kwargs: dict) -> None:
        super().__init__(name, **kwargs)
        self.elements = []
        self.packages = []
        self._collection_map = {}

    def append(self, item: Any):
        """
        Append element or sub-package
        """
        if isinstance(item, Package):
            package: Package = item
            if package.name in self._collection_map:
                raise ValueError(
                    f"Package with SHORT-NAME '{package.name}' already exists in package '{self.name}")
            package.parent = self
            self.packages.append(package)
            self._collection_map[package.name] = package
        elif isinstance(item, ARElement):
            elem: ARElement = item
            if elem.name in self._collection_map:
                raise ValueError(
                    f"Element with SHORT-NAME '{elem.name}' already exists in package '{self.name}'")
            elem.parent = self
            self.elements.append(elem)
            self._collection_map[elem.name] = elem
        else:
            raise TypeError(f"Invalid type {str(type(item))}")

    def make_packages(self, ref: str) -> "Package":
        """
        Recursively creates sub-packages
        """
        if ref.startswith('/'):
            raise ValueError("Reference string can't start with '/'")
        parts = ref.partition('/')
        package = self._collection_map.get(parts[0], None)
        if package is None:
            package = self.create_package(parts[0])
        elif not isinstance(package, Package):
            raise KeyError(f"Item with name '{parts[0]}' already exists but isn't a package")
        if len(parts[2]) > 0:
            return package.make_packages(parts[2])
        else:
            return package

    def create_package(self, name: str, **kwargs) -> "Package":
        """
        Creates new sub-package
        """
        if name in self._collection_map:
            return ValueError(f"Package with name '{name}' already exists")
        package = Package(name, **kwargs)
        self._collection_map[name] = package
        self.packages.append(package)
        package.parent = self
        return package

    def find(self, ref: str) -> Any:
        """
        Finds item by reference
        """
        if ref.startswith('/'):
            ref = ref[1:]
        parts = ref.partition('/')
        item = self._collection_map.get(parts[0], None)
        if item is not None:
            if len(parts[2]) > 0:
                return item.find(parts[2])
        return item

    def update_ref_parts(self, ref_parts: list[str]):
        """
        Utility method used generating XML references
        """
        ref_parts.append(self.name)
        self.parent.update_ref_parts(ref_parts)
