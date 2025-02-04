"""
ARXML writer module
"""
# pylint: disable=consider-using-with
from io import StringIO
from typing import TextIO, Union
import math
import decimal
import autosar.xml.document as ar_document
import autosar.xml.element as ar_element
import autosar.xml.enumeration as ar_enum
# import autosar.xml.exception

# Type aliases

MultiLanguageOverviewParagraph = ar_element.MultiLanguageOverviewParagraph
TupleList = list[tuple[str, str]]
ValueSpeficationElement = Union[ar_element.TextValueSpecification,
                                ar_element.NumericalValueSpecification,
                                ar_element.NotAvailableValueSpecification,
                                ar_element.ArrayValueSpecification,
                                ar_element.RecordValueSpecification,
                                ar_element.ApplicationValueSpecification,
                                ar_element.ConstantReference]


class _XMLWriter:
    def __init__(self, indentation_step: int) -> None:
        self.file_path: str = None
        self.fh: TextIO = None  # pylint: disable=invalid-name
        self.indentation_char: str = ' '
        # Number of characters (spaces) per indendation
        self.indentation_step = indentation_step
        self.indentation_level: int = 0  # current indentation level
        self.indentation_str: str = ''
        self.tag_stack = []  # stack of tag names
        self.line_number: int = 0

    def _str_open(self):
        self.fh = StringIO()
        self.line_number = 1
        self.indentation_level = 0
        self.indentation_str = ''
        self.tag_stack.clear()

    def _open(self, file_path: str):
        self.fh = open(file_path, 'w', encoding='utf-8')
        self.file_path = file_path
        self.line_number = 1
        self.indentation_level = 0
        self.indentation_str = ''
        self.tag_stack.clear()

    def _close(self):
        self.fh.close()

    def _indent(self):
        self.indentation_level += 1
        self.indentation_str = self.indentation_char * \
            (self.indentation_level * self.indentation_step)

    def _dedent(self):
        self.indentation_level -= 1
        if self.indentation_level == 0:
            self.indentation_str = ''
        else:
            self.indentation_str = self.indentation_char * \
                (self.indentation_level * self.indentation_step)

    def _add_line(self, text):
        if self.line_number > 1:
            self.fh.write('\n')
        self.line_number += 1
        self.fh.write(self.indentation_str)
        self.fh.write(text)

    def _add_inline_text(self, text):
        self.fh.write(text)

    def _add_child(self, tag: str, attr: TupleList = None):
        if attr:
            self._add_line(f'<{tag} {self._attr_to_str(attr)}>')
        else:
            self._add_line(f'<{tag}>')
        self.tag_stack.append(tag)
        self._indent()

    def _leave_child(self):
        tag = self.tag_stack.pop()
        self._dedent()
        self._add_line(f'</{tag}>')

    def _begin_line(self, tag: str, attr: None | TupleList = None):
        if self.line_number > 1:
            self.fh.write('\n')
        self.line_number += 1
        self.fh.write(self.indentation_str)
        if attr is None or len(attr) == 0:
            text = f'<{tag}>'
        else:
            text = f'<{tag} {self._attr_to_str(attr)}>'
        self._add_inline_text(text)

    def _end_line(self, tag: str):
        text = f'</{tag}>'
        self.fh.write(text)

    def _add_content(self, tag: str, content: str = '', attr: TupleList = None, inline: bool = False):
        if attr:
            if content:
                text = f'<{tag} {self._attr_to_str(attr)}>{content}</{tag}>'
            else:
                text = f'<{tag} {self._attr_to_str(attr)}/>'
        else:
            if content:
                text = f'<{tag}>{content}</{tag}>'
            else:
                text = f'<{tag}/>'
        if inline:
            self._add_inline_text(text)
        else:
            self._add_line(text)

    def _attr_to_str(self, attr: TupleList) -> str:
        """
        Converts pairs (2-tuples) into attribute XML string
        """
        parts = [f'{elem[0]}="{elem[1]}"' for elem in attr]
        return ' '.join(parts)

    def _format_float(self, value: float) -> str:
        """
        Formats a float into a printable number string.
        The fractional part will automatically be stripped if possible
        """
        if math.isinf(value):
            return '-INF' if value < 0 else 'INF'
        if math.isnan(value):
            return 'NaN'
        else:
            tmp = decimal.Decimal(str(value))
            return tmp.quantize(decimal.Decimal(1)) if tmp == tmp.to_integral() else tmp.normalize()

    def _format_number(self, number: int | float | ar_element.NumericalValue) -> str:
        """
        Converts number to string
        """
        if isinstance(number, int):
            return str(number)
        elif isinstance(number, float):
            return self._format_float(number)
        elif isinstance(number, ar_element.NumericalValue):
            return self._format_numerical_value(number)
        else:
            raise TypeError("Not supported: " + str(type(number)))

    def _format_boolean(self, value: bool) -> str:
        """
        Converts bool to AR:BOOLEAN
        """
        assert isinstance(value, bool)
        return 'true' if value else 'false'

    def _format_numerical_value(self, number: ar_element.NumericalValue) -> str:
        if number.value_format in (ar_enum.ValueFormat.DEFAULT, ar_enum.ValueFormat.DECIMAL):
            return self._format_number(number.value)
        elif number.value_format == ar_enum.ValueFormat.HEXADECIMAL:
            return f"0x{number.value:x}"
        elif number.value_format == ar_enum.ValueFormat.BINARY:
            return f"0b{number.value:b}"
        elif number.value_format == ar_enum.ValueFormat.SCIENTIFIC:
            return f"{number.value:e}"
        else:
            raise NotImplementedError


class Writer(_XMLWriter):
    """
    ARXML writer class
    """

    def __init__(self) -> None:
        super().__init__(indentation_step=2)
        # Elements found in AR:PACKAGE
        self.switcher_collectable = {
            # Package
            'Package': self._write_package,
            # CompuMethod elements
            'CompuMethod': self._write_compu_method,
            # Data type elements
            'ApplicationArrayDataType': self._write_application_array_data_type,
            'ApplicationRecordDataType': self._write_application_record_data_type,
            'ApplicationPrimitiveDataType': self._write_application_primitive_data_type,
            'SwBaseType': self._write_sw_base_type,
            'SwAddrMethod': self._write_sw_addr_method,
            'ImplementationDataType': self._write_implementation_data_type,
            'DataTypeMappingSet': self._write_data_type_mapping_set,
            # DataConstraint elements
            'DataConstraint': self._write_data_constraint,
            # Unit elements
            'Unit': self._write_unit,
            # Constant elements
            'ConstantSpecification': self._write_constant_specification,
        }
        # Value specification elements
        self.switcher_value_specification = {
            'TextValueSpecification': self._write_text_value_specification,
            'NumericalValueSpecification': self._write_numerical_value_specification,
            'NotAvailableValueSpecification': self._write_not_available_value_specification,
            'ArrayValueSpecification': self._write_array_value_specification,
            'RecordValueSpecification': self._write_record_value_specification,
            'ApplicationValueSpecification': self._write_application_value_specification,
            'ConstantReference': self._write_constant_reference,
        }
        # Elements used only for unit test purposes
        self.switcher_non_collectable = {
            # Documentation elements
            'Annotation': self._write_annotation,
            'Break': self._write_break,
            'DocumentationBlock': self._write_documentation_block,
            'EmphasisText': self._write_emphasis_text,
            'IndexEntry': self._write_index_entry,
            'MultilanguageLongName': self._write_multi_language_long_name,
            'MultiLanguageOverviewParagraph': self._write_multi_language_overview_paragraph,
            'MultiLanguageParagraph': self._write_multi_language_paragraph,
            'MultiLanguageVerbatim': self._write_multi_language_verbatim,
            'LanguageLongName': self._write_language_long_name,
            'LanguageParagraph': self._write_language_paragraph,
            'LanguageVerbatim': self._write_language_verbatim,
            'Package': self._write_package,
            'SingleLanguageUnitNames': self._write_single_language_unit_names,
            'Superscript': self._write_superscript,
            'Subscript': self._write_subscript,
            'TechnicalTerm': self._write_technical_term,
            # CompuMethod elements
            'Computation': self._write_computation,
            'CompuRational': self._write_compu_rational,
            'CompuScale': self._write_compu_scale,
            # Constraint elements
            'ScaleConstraint': self._write_scale_constraint,
            'InternalConstraint': self._write_internal_constraint,
            'PhysicalConstraint': self._write_physical_constraint,
            'DataConstraintRule': self._write_data_constraint_rule,
            # DataType and DataDictionary elements
            'SwDataDefPropsConditional': self._write_sw_data_def_props_conditional,
            'SwBaseTypeRef': self._write_sw_base_type_ref,
            'SwBitRepresentation': self._write_sw_bit_represenation,
            'SwTextProps': self._write_sw_text_props,
            'SwPointerTargetProps': self._write_sw_pointer_target_props,
            'SymbolProps': self._write_symbol_props,
            'ImplementationDataTypeElement': self._write_implementation_data_type_element,
            'ApplicationArrayElement': self._write_application_array_element,
            'ApplicationRecordElement': self._write_application_record_element,
            'DataTypeMap': self._write_data_type_map,
            'ValueList': self._write_value_list,
            # CalibrationData elements
            'SwValues': self._write_sw_values,
            'SwAxisCont': self._write_sw_axis_cont,
            'SwValueCont': self._write_sw_value_cont,
            # Reference elements
            'PhysicalDimensionRef': self._write_physical_dimension_ref,
            'ApplicationDataTypeRef': self._write_application_data_type_ref,
            'ConstantRef': self._write_constant_ref,
        }
        self.switcher_all = {}  # All concrete elements (used for unit testing)
        self.switcher_all.update(self.switcher_collectable)
        self.switcher_all.update(self.switcher_value_specification)
        self.switcher_all.update(self.switcher_non_collectable)

    def write_str(self, document: ar_document.Document, skip_root_attr: bool = True) -> str:
        """
        Serializes the document to string.
        """
        self._str_open()
        self._write_document(document, skip_root_attr)
        return self.fh.getvalue()

    def write_file(self, document: ar_document.Document, file_path: str):
        """
        Serialized the document to file
        """
        self._open(file_path)
        self._write_document(document)
        self._close()

    def write_str_elem(self, elem: ar_element.ARObject, tag: str | None = None):
        """
        Writes single ARXML element as string
        """
        self._str_open()
        class_name = elem.__class__.__name__
        write_method = self.switcher_all.get(class_name, None)
        if write_method is not None:
            if tag is not None:
                write_method(elem, tag)
            else:
                write_method(elem)
        else:
            raise NotImplementedError(
                f"Found no writer for class {class_name}")
        return self.fh.getvalue()

    def write_file_elem(self, elem: ar_element.ARElement, file_path: str):
        """
        Writes single ARXML element to file
        """
        self._open(file_path)
        class_name = elem.__class__.__name__
        write_method = self.switcher_collectable.get(class_name, None)
        if write_method is not None:
            write_method(elem)
        else:
            raise NotImplementedError(f"Found no writer for {class_name}")
        self._close()

    # Abstract base classes

    def _write_referrable(self, elem: ar_element.MultiLanguageReferrable):
        """
        Writes group AR:REFERRABLE
        Type: Abstract
        """
        self._add_content('SHORT-NAME', elem.name)

    def _write_multilanguage_referrable(self, elem: ar_element.MultiLanguageReferrable):
        """
        Writes AR:MULTILANGUAGE-REFFERABLE
        Type: Abstract
        """
        if elem.long_name is not None:
            self._write_multi_language_long_name(elem.long_name, 'LONG-NAME')

    def _collect_identifiable_attributes(self, elem: ar_element.Identifiable, attr: TupleList):
        if elem.uuid is not None:
            attr.append(('UUID', elem.uuid))
        if len(attr) > 0:
            return attr
        return None

    def _write_identifiable(self, elem: ar_element.Identifiable) -> None:
        """
        Writes group AR:IDENTIFIABLE
        Type: Abstract
        """
        if elem.desc:
            self._write_multi_language_overview_paragraph(elem.desc, 'DESC')
        if elem.category:
            self._add_content('CATEGORY', elem.category)
        if elem.admin_data:
            self._write_admin_data(elem.admin_data)
        if elem.introduction:
            self._write_documentation_block(elem.introduction, 'INTRODUCTION')
        if elem.annotations:
            self._write_annotations(elem.annotations)

    # AdminData

    def _write_admin_data(self, data: dict) -> None:
        """
        Writes Complex-type AR:ADMIN-DATA
        Type: Concrete
        Tag variants: 'ADMIN-DATA'
        """

    # AUTOSAR Document

    def _write_document(self, document: ar_document.Document, skip_root_attr: bool = False):
        self._add_line('<?xml version="1.0" encoding="utf-8"?>')
        if skip_root_attr:
            self._add_child("AUTOSAR")
        else:
            self._add_child("AUTOSAR", [('xsi:schemaLocation',
                                         f'http://autosar.org/schema/r4.0 {document.schema_file}'),
                                        ('xmlns', 'http://autosar.org/schema/r4.0'),
                                        ('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')])
        if len(document.packages) > 0:
            self._write_packages(document.packages)
        self._leave_child()

    def _write_packages(self, packages: list[ar_element.Package]):
        self._add_child("AR-PACKAGES")
        for package in packages:
            self._write_package(package)
        self._leave_child()

    # AUTOSAR PACKAGE

    def _write_package(self, package: ar_element.Package) -> None:
        """
        Writes AR-PACKAGE
        Type: Concrete
        Tag variants: 'AR-PACKAGE'
        """
        assert isinstance(package, ar_element.Package)
        attr: TupleList = []
        self._collect_identifiable_attributes(package, attr)
        self._add_child("AR-PACKAGE", attr)
        self._write_referrable(package)
        self._write_multilanguage_referrable(package)
        self._write_identifiable(package)
        if len(package.elements) > 0:
            self._write_package_elements(package)
        if len(package.packages) > 0:
            self._write_sub_packages(package)
        self._leave_child()

    def _write_package_elements(self, package: ar_element.Package) -> None:
        self._add_child('ELEMENTS')
        for elem in package.elements:
            class_name = elem.__class__.__name__
            write_method = self.switcher_collectable.get(class_name, None)
            if write_method is not None:
                write_method(elem)
            else:
                raise NotImplementedError(
                    f"Package: Found no writer for {class_name}")
        self._leave_child()

    def _write_sub_packages(self, package: ar_element.Package) -> None:
        self._add_child('AR-PACKAGES')
        for sub_package in package.packages:
            self._write_package(sub_package)
        self._leave_child()

    # Documentation Elements

    def _write_annotation(self, elem: ar_element.Annotation) -> None:
        """
        Writes AR:ANNOTATION
        Type: Concrete
        """
        assert isinstance(elem, ar_element.Annotation)
        tag = 'ANNOTATION'
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            self._write_general_annotation(elem)
            self._leave_child()

    def _write_annotations(self, elements: list[ar_element.Annotation]) -> None:
        """
        Writes an unbounded list of AR:ANNOTATION
        """
        tag = 'ANNOTATIONS'
        if elements:
            for elem in elements:
                self._add_child(tag)
                self._write_annotation(elem)
                self._leave_child()
        else:
            self._add_content(tag)

    def _write_break(self, elem: ar_element.Break, inline=True) -> None:
        """
        Writes AR:BR
        Type: Concrete
        """
        assert isinstance(elem, ar_element.Break)
        self._add_content('BR', '', inline=inline)

    def _write_documentation_block(self, elem: ar_element.DocumentationBlock, tag: str):
        """
        Writes AR:DOCUMENTATION-BLOCK
        Type: Concrete
        Tag Variants: Too many to list
        """
        assert isinstance(elem, ar_element.DocumentationBlock)
        if not elem.elements:
            self._add_content(tag)
        else:
            self._add_child(tag)
            for child_elem in elem.elements:
                if isinstance(child_elem, ar_element.MultiLanguageParagraph):
                    self._write_multi_language_paragraph(child_elem)
                elif isinstance(child_elem, ar_element.MultiLanguageVerbatim):
                    self._write_multi_language_verbatim(child_elem)
                else:
                    raise NotImplementedError(str(type(child_elem)))
            self._leave_child()

    def _write_emphasis_text(self, elem: ar_element.EmphasisText, inline=True):
        """
        Writes AR:EMPHASIS-TEXT
        Type: Concrete
        TagName: E
        """
        assert isinstance(elem, ar_element.EmphasisText)
        attr = self._collect_emphasis_text_attributes(elem)
        if len(elem.elements) == 1 and isinstance(elem.elements[0], str):
            self._add_content('E', elem.elements[0], attr, inline=inline)
        else:
            raise NotImplementedError(
                'EMPHASIS-TEXT currently supports single str element only')

    def _collect_emphasis_text_attributes(self, elem: ar_element.EmphasisText) -> None | TupleList:
        attr: TupleList = []
        if elem.color is not None:
            attr.append(('COLOR', elem.color))
        if elem.font is not None:
            attr.append(('FONT', ar_enum.enum_to_xml(elem.font)))
        if elem.type is not None:
            attr.append(('TYPE', ar_enum.enum_to_xml(elem.type)))
        if len(attr) > 0:
            return attr
        return None

    def _write_index_entry(self, elem: ar_element.IndexEntry, inline=True):
        """
        Writes IndexEntry (AR:INDEX-ENTRY)
        Type: Concrete
        """
        assert isinstance(elem, ar_element.IndexEntry)
        self._add_content('IE', elem.text, inline=inline)

    def _write_technical_term(self, elem: ar_element.TechnicalTerm, inline=True):
        """
        Writes AR:TT
        Type: Concrete
        TagName: TT
        """
        assert isinstance(elem, ar_element.TechnicalTerm)
        attr: TupleList = []
        self._collect_technical_term_attributes(elem, attr)
        self._add_content('TT', elem.text, attr, inline)

    def _collect_technical_term_attributes(self, elem: ar_element.TechnicalTerm, attr: TupleList):
        """
        Collects attributes from attributeGroup AR:TT
        """
        if elem.tex_render is not None:
            attr.append(('TEX-RENDER', elem.tex_render))
        if elem.type is not None:
            attr.append(('TYPE', elem.type))

    def _write_superscript(self, elem: ar_element.Superscript, inline=True):
        """
        Writes Superscript (AR:SUPSCRIPT)
        Type: Concrete
        """
        assert isinstance(elem, ar_element.Superscript)
        self._add_content('SUP', elem.text, inline=inline)

    def _write_subscript(self, elem: ar_element.Subscript, inline=True):
        """
        Writes Subscript (AR:SUPSCRIPT)
        Type: Concrete
        """
        assert isinstance(elem, ar_element.Subscript)
        self._add_content('SUB', elem.text, inline=inline)

    def _write_multi_language_long_name(self, elem: ar_element.MultilanguageLongName, tag: str) -> None:
        """
        Writes complexType AR:MULTILANGUAGE-LONG-NAME
        Type: Concrete
        Tag variants: 'LABEL' | 'LONG-NAME'
        """
        # assert isinstance(elem.tag, str)
        self._add_child(tag)
        for child_elem in elem.elements:
            self._write_language_long_name(child_elem)
        self._leave_child()

    def _write_language_long_name(self, elem: ar_element.LanguageLongName):
        """
        Writes complexType AR:L-LONG-NAME
        Type: Concrete
        """
        assert isinstance(elem, ar_element.LanguageLongName)
        attr: TupleList = []
        self._collect_language_specific_attr(elem, attr)
        tag = 'L-4'
        self._begin_line(tag, attr)
        for part in elem.parts:
            if isinstance(part, str):
                self._add_inline_text(part)
            elif isinstance(part, ar_element.EmphasisText):
                self._write_emphasis_text(part, inline=True)
            elif isinstance(part, ar_element.IndexEntry):
                self._write_index_entry(part, inline=True)
            elif isinstance(part, ar_element.Subscript):
                self._write_subscript(part, inline=True)
            elif isinstance(part, ar_element.Superscript):
                self._write_superscript(part, inline=True)
            elif isinstance(part, ar_element.TechnicalTerm):
                self._write_technical_term(part, inline=True)
            else:
                raise TypeError('Unsupported type: ' + str(type(part)))
        self._end_line(tag)

    def _collect_language_specific_attr(self, elem: ar_element.LanguageSpecific, attr: TupleList) -> None:
        """
        Collects attributes from attributeGroup AR:LANGUAGE-SPECIFIC
        """
        attr.append(('L', ar_enum.enum_to_xml(elem.language))
                    )  # The L attribute is mandatory

    def _write_multi_language_overview_paragraph(self, elem: MultiLanguageOverviewParagraph, tag: str) -> None:
        """
        Writes complexType AR:MULTI-LANGUAGE-OVERVIEW-PARAGRAPH
        Type: Concrete
        Tag variants: 'DESC' | 'ITEM-LABEL' | 'CHANGE' | 'REASON'
        """
        assert isinstance(elem, MultiLanguageOverviewParagraph)
        if tag not in {'DESC', 'ITEM-LABEL', 'CHANGE', 'REASON'}:
            raise ValueError('Invalid tag parameter: ' + tag)
        self._add_child(tag)
        for child_elem in elem.elements:
            self._write_language_overview_paragraph(child_elem)
        self._leave_child()

    def _write_multi_language_verbatim(self, elem: ar_element.MultiLanguageVerbatim) -> None:
        """
        Writes complexType AR:MULTI-LANGUAGE-VERBATIM
        Type: Concrete
        Tag variants: 'VERBATIM'
        """
        assert isinstance(elem, ar_element.MultiLanguageVerbatim)
        attr: TupleList = []
        self._collect_document_view_selectable_attributes(elem, attr)
        self._collect_paginateable_attributes(elem, attr)
        self._collect_multi_language_verbatim_attributes(elem, attr)
        self._add_child('VERBATIM', attr)
        for child_elem in elem.elements:
            self._write_language_verbatim(child_elem)
        self._leave_child()

    def _collect_multi_language_verbatim_attributes(self,
                                                    elem: ar_element.MultiLanguageVerbatim,
                                                    attr: TupleList):
        """
        Collects attributes from attributeGroup AR:MULTI-LANGUAGE-VERBATIM
        """
        if elem.allow_break is not None:
            attr.append(('ALLOW-BREAK', elem.allow_break))
        if elem.float is not None:
            attr.append(('FLOAT', ar_enum.enum_to_xml(elem.float)))
        if elem.help_entry is not None:
            attr.append(('HELP-ENTRY', elem.help_entry))
        if elem.page_wide is not None:
            attr.append(('PGWIDE', ar_enum.enum_to_xml(elem.page_wide)))

    def _write_language_overview_paragraph(self, elem: ar_element.LanguageOverviewParagraph) -> None:
        """
        Writes complexType AR:L-OVERVIEW-PARAGRAPH
        Type: Concrete
        Tag variants: 'L-2'
        """
        assert isinstance(elem, ar_element.LanguageOverviewParagraph)
        attr: TupleList = []
        self._collect_language_specific_attr(elem, attr)
        tag = 'L-2'
        self._begin_line(tag, attr)
        for part in elem.parts:
            if isinstance(part, str):
                self._add_inline_text(part)
            elif isinstance(part, ar_element.Break):
                self._write_break(part, inline=True)
            elif isinstance(part, ar_element.EmphasisText):
                self._write_emphasis_text(part, inline=True)
            elif isinstance(part, ar_element.IndexEntry):
                self._write_index_entry(part, inline=True)
            elif isinstance(part, ar_element.Subscript):
                self._write_subscript(part, inline=True)
            elif isinstance(part, ar_element.Superscript):
                self._write_superscript(part, inline=True)
            elif isinstance(part, ar_element.TechnicalTerm):
                self._write_technical_term(part, inline=True)
            else:
                raise TypeError('Unsupported type: ' + str(type(part)))
        self._end_line(tag)

    def _write_language_paragraph(self, elem: ar_element.LanguageParagraph) -> None:
        """
        Writes complexType AR:L-PARAGRAPH
        Type: Concrete
        Tag variants: 'L-1'
        """
        assert isinstance(elem, ar_element.LanguageParagraph)
        attr: TupleList = []
        self._collect_language_specific_attr(elem, attr)
        tag = 'L-1'
        self._begin_line(tag, attr)
        for part in elem.parts:
            if isinstance(part, str):
                self._add_inline_text(part)
            elif isinstance(part, ar_element.Break):
                self._write_break(part, inline=True)
            elif isinstance(part, ar_element.EmphasisText):
                self._write_emphasis_text(part, inline=True)
            elif isinstance(part, ar_element.IndexEntry):
                self._write_index_entry(part, inline=True)
            elif isinstance(part, ar_element.Subscript):
                self._write_subscript(part, inline=True)
            elif isinstance(part, ar_element.Superscript):
                self._write_superscript(part, inline=True)
            elif isinstance(part, ar_element.TechnicalTerm):
                self._write_technical_term(part, inline=True)
            else:
                raise TypeError('Unsupported type: ' + str(type(part)))
        self._end_line(tag)

    def _write_language_verbatim(self, elem: ar_element.LanguageVerbatim) -> None:
        """
        Writes complexType AR:L-VERBATIM
        Type: Concrete
        Tag variants: 'L-5'
        """
        assert isinstance(elem, ar_element.LanguageVerbatim)
        attr: TupleList = []
        self._collect_language_specific_attr(elem, attr)
        tag = 'L-5'
        self._begin_line(tag, attr)
        for part in elem.parts:
            if isinstance(part, str):
                self._add_inline_text(part)
            elif isinstance(part, ar_element.Break):
                self._write_break(part, inline=True)
            elif isinstance(part, ar_element.EmphasisText):
                self._write_emphasis_text(part, inline=True)
            elif isinstance(part, ar_element.TechnicalTerm):
                self._write_technical_term(part, inline=True)
            else:
                raise TypeError('Unsupported type: ' + str(type(part)))
        self._end_line(tag)

    def _write_multi_language_paragraph(self, elem: ar_element.MultiLanguageParagraph) -> None:
        """
        Writes complexType AR:MULTI-LANGUAGE-PARAGRAPH
        Type: Concrete
        Tag variants: 'P'
        """
        assert isinstance(elem, ar_element.MultiLanguageParagraph)
        attr: TupleList = []
        self._collect_document_view_selectable_attributes(elem, attr)
        self._collect_paginateable_attributes(elem, attr)
        self._collect_multi_language_paragraph_attributes(elem, attr)
        self._add_child('P', attr)
        for child_elem in elem.elements:
            self._write_language_paragraph(child_elem)
        self._leave_child()

    def _collect_multi_language_paragraph_attributes(self,
                                                     elem: ar_element.MultiLanguageParagraph,
                                                     attr: TupleList):
        """
        Collects attributes from attributeGroup AR:MULTI-LANGUAGE-PARAGRAPH
        """
        if elem.help_entry is not None:
            attr.append(('HELP-ENTRY', elem.help_entry))

    def _collect_document_view_selectable_attributes(self,
                                                     elem: ar_element.DocumentViewSelectable,
                                                     attr: TupleList):
        """
        Collects attributes from attributeGroup AR:DOCUMENT-VIEW-SELECTABLE
        """
        if elem.semantic_information is not None:
            attr.append(('SI', elem.semantic_information))
        if elem.view is not None:
            attr.append(('VIEW', elem.view))

    def _collect_paginateable_attributes(self,
                                         elem: ar_element.Paginateable,
                                         attr: TupleList):
        """
        Collects attributes from attributeGroup AR:PAGINATEABLE
        """
        if elem.page_break is not None:
            attr.append(('BREAK', ar_enum.enum_to_xml(elem.page_break)))
        if elem.keep_with_previous is not None:
            attr.append(
                ('KEEP-WITH-PREVIOUS', ar_enum.enum_to_xml(elem.keep_with_previous)))

    def _write_general_annotation(self, elem: ar_element.GeneralAnnotation) -> None:
        """
        Writes Group AR:GENERAL-ANNOTATION
        """
        if elem.label is not None:
            self._write_multi_language_long_name(elem.label, 'LABEL')
        if elem.origin is not None:
            self._add_content('ANNOTATION-ORIGIN', str(elem.origin))
        if elem.text is not None:
            self._write_documentation_block(elem.text, 'ANNOTATION-TEXT')

    def _write_single_language_unit_names(self, elem: ar_element.SingleLanguageUnitNames, tag: str) -> None:
        """
        Writes complex type AR:SINGLE-LANGUAGE-UNIT-NAMES
        Type: Concrete
        Tab variants: 'PRM-UNIT' | 'UNIT-DISPLAY-NAME' | 'UNIT-DISPLAY-NAME' | 'DISPLAY-NAME'
        """
        assert isinstance(elem, ar_element.SingleLanguageUnitNames)
        self._begin_line(tag)
        for part in elem.parts:
            if isinstance(part, str):
                self._add_inline_text(part)
            elif isinstance(part, ar_element.Subscript):
                self._write_subscript(part)
            elif isinstance(part, ar_element.Superscript):
                self._write_superscript(part)
            else:
                raise TypeError('Unsupported type: ' + str(type(part)))
        self._end_line(tag)

    # CompuMethod elements

    def _write_compu_method(self, elem: ar_element.CompuMethod) -> None:
        """
        Writes complex type AR:COMPU-METHOD
        Type: Concrete
        Tab variants: 'COMPU-METHOD'
        """
        assert isinstance(elem, ar_element.CompuMethod)
        attr: TupleList = []
        self._collect_identifiable_attributes(elem, attr)
        self._add_child("COMPU-METHOD", attr)
        self._write_referrable(elem)
        self._write_multilanguage_referrable(elem)
        self._write_identifiable(elem)
        self._write_compu_method_group(elem)
        self._leave_child()

    def _write_compu_method_group(self, elem: ar_element.CompuMethod) -> None:
        """
        Writes group AR:COMPU-METHOD
        """
        if elem.display_format is not None:
            self._add_content("DISPLAY-FORMAT", str(elem.display_format))
        if elem.unit_ref is not None:
            self._write_unit_ref(elem.unit_ref)
        if elem.int_to_phys is not None:
            self._write_computation(elem.int_to_phys, "COMPU-INTERNAL-TO-PHYS")
        if elem.phys_to_int is not None:
            self._write_computation(elem.phys_to_int, "COMPU-PHYS-TO-INTERNAL")

    def _write_computation(self, elem: ar_element.Computation, tag: str) -> None:
        """
        Writes AR:COMPU
        Type: Concrete
        Tag variants: 'COMPU-INTERNAL-TO-PHYS', 'COMPU-PHYS-TO-INTERNAL'
        """
        self._add_child(tag)
        if elem.compu_scales is not None:
            self._add_child("COMPU-SCALES")
            for compu_scale in elem.compu_scales:
                self._write_compu_scale(compu_scale)
            self._leave_child()
        if elem.default_value is not None:
            self._write_compu_const(elem.default_value, "COMPU-DEFAULT-VALUE")
        self._leave_child()

    def _write_compu_scale(self, elem: ar_element.CompuScale) -> None:
        """
        Writes AR:COMPU-SCALE
        Type: Concrete
        Tag variants: 'COMPU-SCALE'
        """
        assert isinstance(elem, ar_element.CompuScale)
        tag = "COMPU-SCALE"
        if elem.is_empty:
            self._add_content(tag)
            return
        self._add_child(tag)
        if elem.label is not None:
            self._add_content("SHORT-LABEL", str(elem.label))
        if elem.symbol is not None:
            self._add_content("SYMBOL", str(elem.symbol))
        if elem.desc is not None:
            self._write_multi_language_overview_paragraph(elem.desc, "DESC")
        if elem.mask is not None:
            self._add_content("MASK", int(elem.mask))
        if elem.lower_limit is not None:
            self._write_limit("LOWER-LIMIT", elem.lower_limit, elem.lower_limit_type)
        if elem.upper_limit is not None:
            self._write_limit("UPPER-LIMIT", elem.upper_limit, elem.upper_limit_type)
        if elem.inverse_value is not None:
            self._write_compu_const(elem.inverse_value, "COMPU-INVERSE-VALUE")
        if elem.content is not None:
            if isinstance(elem.content, ar_element.CompuConst):
                self._write_compu_const(elem.content, "COMPU-CONST")
            elif isinstance(elem.content, ar_element.CompuRational):
                self._write_compu_rational(elem.content)
        self._leave_child()

    def _write_limit(self,
                     tag: str,
                     limit: int | float,
                     limit_type: ar_enum.IntervalType):
        assert limit is not None
        assert limit_type is not None
        attr: TupleList = [("INTERVAL-TYPE", ar_enum.enum_to_xml(limit_type))]
        if isinstance(limit, float):
            text = self._format_float(limit)
        elif isinstance(limit, int):
            text = str(limit)
        else:
            raise TypeError(f"Unsupported type: {str(type(limit))}")
        self._add_content(tag, text, attr)

    def _write_compu_const(self, elem: ar_element.CompuConst, tag) -> None:
        """
        Writes AR:COMPU-CONST
        Type: Concrete
        Tag variants: 'COMPU-CONST', 'COMPU-INVERSE-VALUE', 'COMPU-DEFAULT-VALUE'
        """
        assert isinstance(elem, ar_element.CompuConst)
        self._add_child(tag)
        if isinstance(elem.value, str):
            self._add_content("VT", elem.value)
        elif isinstance(elem.value, float):
            self._add_content("V", self._format_float(elem.value))
        elif isinstance(elem.value, int):
            self._add_content("V", elem.value)
        else:
            raise TypeError(f"Unsupported type: {str(type(elem.value))}")
        self._leave_child()

    def _write_compu_rational(self, elem: ar_element.CompuRational) -> None:
        """
        Writes AR:COMPU-RATIONAL-COEFFS
        Type: Concrete
        Tag variants: 'COMPU-RATIONAL-COEFFS'
        """
        assert isinstance(elem, ar_element.CompuRational)
        tag = 'COMPU-RATIONAL-COEFFS'
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            if elem.numerator is not None:
                self._add_child('COMPU-NUMERATOR')
                self._write_numerator_denominator_values(elem.numerator)
                self._leave_child()
            if elem.denominator is not None:
                self._add_child('COMPU-DENOMINATOR')
                self._write_numerator_denominator_values(elem.denominator)
                self._leave_child()
            self._leave_child()

    def _write_numerator_denominator_values(self, value: int | float | tuple):
        if isinstance(value, tuple):
            for inner_value in value:
                if isinstance(inner_value, float):
                    content = self._format_float(inner_value)
                else:
                    content = str(inner_value)
                self._add_content('V', content)
        else:
            if isinstance(value, float):
                content = self._format_float(value)
            else:
                content = str(value)
            self._add_content('V', content)

    # Constraint elements

    def _write_data_constraint(self, elem: ar_element.DataConstraint) -> None:
        """
        Writes complex type AR:DATA-CONSTR
        Type: Concrete
        Tab variants: 'DATA-CONSTR-RULE'
        """
        assert isinstance(elem, ar_element.DataConstraint)
        attr: TupleList = []
        self._collect_identifiable_attributes(elem, attr)
        self._add_child("DATA-CONSTR", attr)
        self._write_referrable(elem)
        self._write_multilanguage_referrable(elem)
        self._write_identifiable(elem)
        self._write_data_constraint_group(elem)
        self._leave_child()

    def _write_data_constraint_group(self, elem: ar_element.DataConstraint) -> None:
        """
        Writes group AR:DATA-CONSTR-RULE
        Type: Abstract
        """
        if elem.rules:
            self._add_child("DATA-CONSTR-RULES")
            for rule in elem.rules:
                self._write_data_constraint_rule(rule)
            self._leave_child()

    def _write_data_constraint_rule(self, elem: ar_element.DataConstraintRule) -> None:
        """
        Writes complex type AR:DATA-CONSTR-RULE
        Type: Concrete
        Tag variants: 'DATA-CONSTR-RULE'
        """
        tag = "DATA-CONSTR-RULE"
        assert isinstance(elem, ar_element.DataConstraintRule)
        if elem.is_empty:
            self._add_content(tag)
            return
        self._add_child(tag)
        if elem.level is not None:
            self._add_content("CONSTR-LEVEL", str(elem.level))
        if elem.physical is not None:
            self._write_physical_constraint(elem.physical)
        if elem.internal is not None:
            self._write_internal_constraint(elem.internal)
        self._leave_child()

    def _write_internal_constraint(self, elem: ar_element.InternalConstraint) -> None:
        """
        Writes complex type AR:INTERNAL-CONSTRS
        Type: Concrete
        Tag variants: 'INTERNAL-CONSTRS'
        """
        tag = "INTERNAL-CONSTRS"
        assert isinstance(elem, ar_element.InternalConstraint)
        if elem.is_empty:
            self._add_content(tag)
            return
        self._add_child(tag)
        self._write_constraint_base(elem)
        self._leave_child()

    def _write_physical_constraint(self, elem: ar_element.PhysicalConstraint) -> None:
        """
        Writes complex type AR:PHYS-CONSTRS
        Type: Concrete
        Tag variants: 'PHYS-CONSTRS'
        """
        tag = "PHYS-CONSTRS"
        assert isinstance(elem, ar_element.PhysicalConstraint)
        if elem.is_empty:
            self._add_content(tag)
            return
        self._add_child(tag)
        self._write_constraint_base(elem)
        if elem.unit_ref is not None:
            self._write_unit_ref(elem.unit_ref)
        self._leave_child()

    def _write_constraint_base(self,
                               elem: ar_element.InternalConstraint | ar_element.PhysicalConstraint) -> None:
        """
        Writes elements common for both AR:INTERNAL-CONSTRS and AR:PHYS-CONSTRS
        Type: Abstract
        """
        if elem.lower_limit is not None:
            self._write_limit("LOWER-LIMIT", elem.lower_limit, elem.lower_limit_type)
        if elem.upper_limit is not None:
            self._write_limit("UPPER-LIMIT", elem.upper_limit, elem.upper_limit_type)
        if elem.scale_constrs:
            self._add_child("SCALE-CONSTRS")
            for scale_constr in elem.scale_constrs:
                self._write_scale_constraint(scale_constr)
            self._leave_child()
        if elem.max_gradient is not None:
            self._add_content("MAX-GRADIENT", self._format_number(elem.max_gradient))
        if elem.max_diff is not None:
            self._add_content("MAX-DIFF", self._format_number(elem.max_diff))
        if elem.monotony is not None:
            self._add_content("MONOTONY", ar_enum.enum_to_xml(elem.monotony))

    def _write_scale_constraint(self, elem: ar_element.ScaleConstraint) -> None:
        """
        Writes complex type AR:SCALE-CONSTR
        Type: Concrete
        Tag variants: 'SCALE-CONSTR'
        """
        tag = "SCALE-CONSTR"
        assert isinstance(elem, ar_element.ScaleConstraint)
        attr: TupleList = []
        if elem.validity is not None:
            attr.append(("VALIDITY", ar_enum.enum_to_xml(elem.validity)))
        if elem.is_empty:
            self._add_content(tag, attr=attr)
            return
        self._add_child(tag, attr)
        if elem.label is not None:
            self._add_content("SHORT-LABEL", elem.label)
        if elem.desc is not None:
            self._write_multi_language_overview_paragraph(elem.desc, "DESC")
        if elem.lower_limit is not None:
            self._write_limit("LOWER-LIMIT", elem.lower_limit, elem.lower_limit_type)
        if elem.upper_limit is not None:
            self._write_limit("UPPER-LIMIT", elem.upper_limit, elem.upper_limit_type)
        self._leave_child()

    # Unit elements

    def _write_unit(self, elem: ar_element.Unit) -> None:
        """
        Writes complex type AR:UNIT
        Type: Concrete
        Tag variants: 'UNIT'
        """
        assert isinstance(elem, ar_element.Unit)
        attr: TupleList = []
        self._collect_identifiable_attributes(elem, attr)
        self._add_child('UNIT', attr)
        self._write_referrable(elem)
        self._write_multilanguage_referrable(elem)
        self._write_identifiable(elem)
        self._write_unit_group(elem)
        self._leave_child()

    def _write_unit_group(self, elem: ar_element.Unit) -> None:
        if elem.display_name is not None:
            self._write_single_language_unit_names(elem.display_name, "DISPLAY-NAME")
        if elem.factor is not None:
            self._add_content("FACTOR-SI-TO-UNIT", self._format_float(elem.factor))
        if elem.offset is not None:
            self._add_content("OFFSET-SI-TO-UNIT", self._format_float(elem.offset))
        if elem.physical_dimension_ref is not None:
            self._write_physical_dimension_ref(elem.physical_dimension_ref)

    # Data type elements

    def _write_sw_addr_method(self, elem: ar_element.SwAddrMethod) -> None:
        """
        Writes complex type AR:SW-ADDR-METHOD
        Type: Concrete
        Tag variants: 'SW-ADDR-METHOD'
        """
        assert isinstance(elem, ar_element.SwAddrMethod)
        attr: TupleList = []
        self._collect_identifiable_attributes(elem, attr)
        self._add_child('SW-ADDR-METHOD', attr)
        self._write_referrable(elem)
        self._write_multilanguage_referrable(elem)
        self._write_identifiable(elem)
        self._write_sw_addr_method_group(elem)
        self._leave_child()

    def _write_sw_addr_method_group(self, elem: ar_element.SwAddrMethod) -> None:
        """
        Writes group AR:SW-ADDR-METHOD
        """
        if elem.memory_allocation_keyword_policy:
            pass  # Not yet implemented
        if elem.options:
            pass  # Not yet implemented
        if elem.section_initialization_policy:
            pass  # Not yet implemented
        if elem.section_type:
            pass  # Not yet implemented

    def _write_sw_base_type(self, elem: ar_element.SwBaseType) -> None:
        """
        Writes Complex-type AR:SW-BASE-TYPE
        Type: Concrete
        Tag variants: 'SW-BASE-TYPE'
        """
        assert isinstance(elem, ar_element.SwBaseType)
        attr: TupleList = []
        self._collect_identifiable_attributes(elem, attr)
        self._add_child('SW-BASE-TYPE', attr)
        self._write_referrable(elem)
        self._write_multilanguage_referrable(elem)
        self._write_identifiable(elem)
        self._write_base_type(elem)
        self._leave_child()

    def _write_base_type(self, elem: ar_element.SwBaseType) -> None:
        """
        Writes groups AR:BASE-TYPE and AR:BASE-TYPE-DIRECT-DEFINITION
        """
        if elem.size is not None:
            self._add_content('BASE-TYPE-SIZE', int(elem.size))
        if elem.max_size is not None:
            self._add_content('MAX-BASE-TYPE-SIZE', int(elem.max_size))
        if elem.encoding is not None:
            self._add_content('BASE-TYPE-ENCODING', str(elem.encoding))
        if elem.alignment is not None:
            self._add_content('MEM-ALIGNMENT', int(elem.alignment))
        if elem.byte_order is not None:
            self._add_content(
                'BYTE-ORDER', ar_enum.enum_to_xml(elem.byte_order))
        if elem.native_declaration is not None:
            self._add_content('NATIVE-DECLARATION',
                              str(elem.native_declaration))

    def _write_sw_data_def_props(self, elem: ar_element.SwDataDefProps, tag: str) -> None:
        """
        Writes complex type AR:SW-DATA-DEF-PROPS
        Type: Concrete
        Tag Variants: 'SW-DATA-DEF-PROPS', 'NETWORK-REPRESENTATION'
        """
        assert isinstance(elem, ar_element.SwDataDefProps)
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            if len(elem) > 0:
                self._add_child("SW-DATA-DEF-PROPS-VARIANTS")
                for child_elem in iter(elem):
                    self._write_sw_data_def_props_conditional(child_elem)
                self._leave_child()
            self._leave_child()

    def _write_sw_data_def_props_conditional(self, elem: ar_element.SwDataDefPropsConditional) -> None:
        """
        Writes Complex-type AR:SW-DATA-DEF-PROPS-CONDITIONAL
        Type: Concrete
        Tag variants: 'SW-DATA-DEF-PROPS-CONDITIONAL'
        """
        assert isinstance(elem, ar_element.SwDataDefPropsConditional)
        tag = 'SW-DATA-DEF-PROPS-CONDITIONAL'
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            self._write_sw_data_def_props_content(elem)
            self._leave_child()

    def _write_sw_data_def_props_content(self, elem: ar_element.SwDataDefPropsConditional) -> None:
        """
        Writes Group SW-DATA-DEF-PROPS-CONTENT
        Type: Abstract
        """
        if elem.display_presentation is not None:
            self._add_content('DISPLAY-PRESENTATION',
                              ar_enum.enum_to_xml(elem.display_presentation))
        if elem.step_size is not None:
            self._add_content('STEP-SIZE', self._format_float(elem.step_size))
        if elem.annotations:
            self._write_annotations(elem.annotations)
        if elem.sw_addr_method_ref is not None:
            self._write_sw_addr_method_ref(elem.sw_addr_method_ref)
        if elem.alignment is not None:
            self._add_content('SW-ALIGNMENT', elem.alignment)
        if elem.base_type_ref is not None:
            self._write_sw_base_type_ref(elem.base_type_ref)
        if elem.bit_representation is not None:
            self._write_sw_bit_represenation(elem.bit_representation)
        if elem.calibration_access is not None:
            self._add_content('SW-CALIBRATION-ACCESS',
                              ar_enum.enum_to_xml(elem.calibration_access))
        if elem.text_props is not None:
            self._write_sw_text_props(elem.text_props)
        if elem.compu_method_ref is not None:
            self._write_compu_method_ref(elem.compu_method_ref)
        if elem.display_format is not None:
            self._add_content('DISPLAY-FORMAT', elem.display_format)
        if elem.data_constraint_ref is not None:
            self._write_data_constraint_ref(elem.data_constraint_ref)
        if elem.impl_data_type_ref is not None:
            self._write_impl_data_type_ref(elem.impl_data_type_ref)
        if elem.impl_policy is not None:
            self._add_content('SW-IMPL-POLICY',
                              ar_enum.enum_to_xml(elem.impl_policy))
        if elem.additional_native_type_qualifier is not None:
            self._add_content('ADDITIONAL-NATIVE-TYPE-QUALIFIER',
                              str(elem.additional_native_type_qualifier))
        if elem.intended_resolution is not None:
            self._add_content('SW-INTENDED-RESOLUTION',
                              self._format_number(elem.intended_resolution))
        if elem.interpolation_method is not None:
            self._add_content('SW-INTERPOLATION-METHOD', str(elem.interpolation_method))
        if elem.is_virtual is not None:
            self._add_content('SW-IS-VIRTUAL', self._format_boolean(elem.is_virtual))
        if elem.ptr_target_props is not None:
            self._write_sw_pointer_target_props(elem.ptr_target_props)
        if elem.unit_ref is not None:
            self._write_unit_ref(elem.unit_ref)

    def _write_sw_bit_represenation(self, elem: ar_element.SwBitRepresentation) -> None:
        """
        Writes AR:SW-BIT-REPRESENTATION
        Type: Concrete
        Tag Variants: 'SW-BIT-REPRESENTATION'
        """
        tag = 'SW-BIT-REPRESENTATION'
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            if elem.position is not None:
                self._add_content('BIT-POSITION', str(elem.position))
            if elem.num_bits is not None:
                self._add_content('NUMBER-OF-BITS', str(elem.num_bits))
            self._leave_child()

    def _write_sw_text_props(self, elem: ar_element.SwTextProps) -> None:
        """
        Writes AR:SW-TEXT-PROPS
        Type: Concrete
        Tag Variants: 'SW-TEXT-PROPS'
        """
        tag = 'SW-TEXT-PROPS'
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            if elem.array_size_semantics is not None:
                self._add_content('ARRAY-SIZE-SEMANTICS', ar_enum.enum_to_xml(elem.array_size_semantics))
            if elem.max_text_size is not None:
                self._add_content('SW-MAX-TEXT-SIZE', int(elem.max_text_size))
            if elem.base_type_ref is not None:
                self._write_sw_base_type_ref(elem.base_type_ref)
            if elem.fill_char is not None:
                self._add_content('SW-FILL-CHARACTER', int(elem.fill_char))
            self._leave_child()

    def _write_sw_pointer_target_props(self, elem: ar_element.SwPointerTargetProps) -> None:
        """
        Writes AR:SW-POINTER-TARGET-PROPS
        Type: Concrete
        Tag Variants: 'SW-POINTER-TARGET-PROPS'
        """
        tag = 'SW-POINTER-TARGET-PROPS'
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            if elem.target_category is not None:
                self._add_content("TARGET-CATEGORY", str(elem.target_category))
            if elem.sw_data_def_props is not None:
                self._write_sw_data_def_props(elem.sw_data_def_props, "SW-DATA-DEF-PROPS")
            if elem.function_ptr_signature_ref is not None:
                self._write_function_ptr_signature_ref(elem.function_ptr_signature_ref)
            self._leave_child()

    def _write_symbol_props(self, elem: ar_element.SymbolProps, tag: str) -> None:
        """
        Writes complex type AR:SYMBOL-PROPS
        Type: Concrete
        Tag Variants: 'SYMBOL-PROPS', 'EVENT-SYMBOL-PROPS'
        """
        assert isinstance(elem, ar_element.SymbolProps)
        self._add_child(tag)
        self._write_referrable(elem)
        self._write_implementation_props(elem)
        self._leave_child()

    def _write_implementation_props(self, elem: ar_element.ImplementationProps) -> None:
        """
        Writes group AR:IMPLEMENTATION-PROPS
        Type: Abstract
        """
        if elem.symbol is not None:
            self._add_content("SYMBOL", str(elem.symbol))

    def _write_implementation_data_type_element(self, elem: ar_element.ImplementationDataTypeElement) -> None:
        """
        Writes complex type AR:IMPLEMENTATION-DATA-TYPE-ELEMENT
        Type: Concrete
        Tag variants: 'IMPLEMENTATION-DATA-TYPE-ELEMENT'
        """
        assert isinstance(elem, ar_element.ImplementationDataTypeElement)
        self._add_child("IMPLEMENTATION-DATA-TYPE-ELEMENT")
        self._write_referrable(elem)
        self._write_multilanguage_referrable(elem)
        self._write_identifiable(elem)
        self.__write_implementation_data_type_element_group(elem)
        self._leave_child()

    def __write_implementation_data_type_element_group(self, elem: ar_element.ImplementationDataTypeElement) -> None:
        """
        Writes group AR:IMPLEMENTATION-DATA-TYPE-ELEMENT
        Type: Abstract
        """
        if elem.array_impl_policy is not None:
            self._add_content("ARRAY-IMPL-POLICY", ar_enum.enum_to_xml(elem.array_impl_policy))
        if elem.array_size is not None:
            self._add_content("ARRAY-SIZE", str(elem.array_size))
        if elem.array_size_handling is not None:
            self._add_content("ARRAY-SIZE-HANDLING", ar_enum.enum_to_xml(elem.array_size_handling))
        if elem.array_size_semantics is not None:
            self._add_content("ARRAY-SIZE-SEMANTICS", ar_enum.enum_to_xml(elem.array_size_semantics))
        if elem.is_optional is not None:
            self._add_content("IS-OPTIONAL", self._format_boolean(elem.is_optional))
        if len(elem.sub_elements) > 0:
            self._add_child("SUB-ELEMENTS")
            for sub_elem in elem.sub_elements:
                self._write_implementation_data_type_element(sub_elem)
            self._leave_child()
        if elem.sw_data_def_props is not None:
            self._write_sw_data_def_props(elem.sw_data_def_props, "SW-DATA-DEF-PROPS")

    def _write_implementation_data_type(self, elem: ar_element.ImplementationDataType) -> None:
        """
        Writes complex type AR:IMPLEMENTATION-DATA-TYPE
        Type: Concrete
        Tag variants: 'IMPLEMENTATION-DATA-TYPE'
        """
        assert isinstance(elem, ar_element.ImplementationDataType)
        self._add_child("IMPLEMENTATION-DATA-TYPE")
        self._write_referrable(elem)
        self._write_multilanguage_referrable(elem)
        self._write_identifiable(elem)
        self._write_autosar_data_type(elem)
        self._write_implementation_data_type_group(elem)
        self._leave_child()

    def _write_implementation_data_type_group(self, elem: ar_element.ImplementationDataType) -> None:
        """
        Writes group AR:IMPLEMENTATION-DATA-TYPE
        Type: Abstract
        """
        if elem.dynamic_array_size_profile is not None:
            self._add_content("DYNAMIC-ARRAY-SIZE-PROFILE", str(elem.dynamic_array_size_profile))
        if elem.is_struct_with_optional_element is not None:
            self._add_content("IS-STRUCT-WITH-OPTIONAL-ELEMENT",
                              self._format_boolean(elem.is_struct_with_optional_element))
        if len(elem.sub_elements) > 0:
            self._add_child("SUB-ELEMENTS")
            for sub_elem in elem.sub_elements:
                self._write_implementation_data_type_element(sub_elem)
            self._leave_child()
        if elem.symbol_props is not None:
            self._write_symbol_props(elem.symbol_props, "SYMBOL-PROPS")
        if elem.type_emitter is not None:
            self._add_content("TYPE-EMITTER", str(elem.type_emitter))

    def _write_autosar_data_type(self, elem: ar_element.AutosarDataType) -> None:
        """
        Writes group AR:AUTOSAR-DATA-TYPE
        Type: Abstract
        """
        if elem.sw_data_def_props is not None:
            self._write_sw_data_def_props(elem.sw_data_def_props, "SW-DATA-DEF-PROPS")

    def _write_data_prototype(self, elem: ar_element.DataPrototype) -> None:
        """
        Writes group AR:DATA-PROTOTYPE
        Type: Abstract
        """
        if elem.sw_data_def_props is not None:
            self._write_sw_data_def_props(elem.sw_data_def_props, "SW-DATA-DEF-PROPS")

    def _write_application_primitive_data_type(self, elem: ar_element.ApplicationPrimitiveDataType) -> None:
        """
        Writes complex type AR:APPLICATION-PRIMITIVE-DATA-TYPE
        Type: Concrete
        Tag variants: 'APPLICATION-PRIMITIVE-DATA-TYPE'
        """
        assert isinstance(elem, ar_element.ApplicationPrimitiveDataType)
        self._add_child("APPLICATION-PRIMITIVE-DATA-TYPE")
        self._write_referrable(elem)
        self._write_multilanguage_referrable(elem)
        self._write_identifiable(elem)
        self._write_autosar_data_type(elem)
        self._leave_child()

    def _write_application_composite_element_data_prototype(
            self,
            elem: ar_element.ApplicationCompositeElementDataPrototype) -> None:
        """
        Writes group AR:APPLICATION-COMPOSITE-ELEMENT-DATA-PROTOTYPE
        Type: Abstract
        """
        assert isinstance(elem, ar_element.ApplicationCompositeElementDataPrototype)
        if elem.type_ref is not None:
            self._write_application_data_type_ref(elem.type_ref, 'TYPE-TREF')

    def _write_application_array_element(self, elem: ar_element.ApplicationArrayElement) -> None:
        """
        Writes complex type AR:APPLICATION-ARRAY-ELEMENT
        Type: Concrete
        Tag variants: 'ELEMENT'
        """
        assert isinstance(elem, ar_element.ApplicationArrayElement)
        self._add_child("ELEMENT")
        self._write_referrable(elem)
        self._write_multilanguage_referrable(elem)
        self._write_identifiable(elem)
        self._write_data_prototype(elem)
        self._write_application_composite_element_data_prototype(elem)
        self._write_application_array_element_group(elem)
        self._leave_child()

    def _write_application_array_element_group(self, elem: ar_element.ApplicationArrayElement) -> None:
        """
        Writes group AR:APPLICATION-ARRAY-ELEMENT
        Type: Abstract
        """
        if elem.array_size_handling is not None:
            self._add_content("ARRAY-SIZE-HANDLING", ar_enum.enum_to_xml(elem.array_size_handling))
        if elem.array_size_semantics is not None:
            self._add_content("ARRAY-SIZE-SEMANTICS", ar_enum.enum_to_xml(elem.array_size_semantics))
        if elem.index_data_type_ref is not None:
            self._write_index_data_type_ref(elem.index_data_type_ref)
        if elem.max_number_of_elements is not None:
            self._add_content("MAX-NUMBER-OF-ELEMENTS", elem.max_number_of_elements)

    def _write_application_record_element(self, elem: ar_element.ApplicationRecordElement) -> None:
        """
        Writes complex type AR:APPLICATION-RECORD-ELEMENT
        Type: Concrete
        Tag variants: 'APPLICATION-RECORD-ELEMENT'
        """
        assert isinstance(elem, ar_element.ApplicationRecordElement)
        self._add_child("APPLICATION-RECORD-ELEMENT")
        self._write_referrable(elem)
        self._write_multilanguage_referrable(elem)
        self._write_identifiable(elem)
        self._write_data_prototype(elem)
        self._write_application_composite_element_data_prototype(elem)
        self._write_application_record_element_group(elem)
        self._leave_child()

    def _write_application_record_element_group(self, elem: ar_element.ApplicationRecordElement) -> None:
        """
        Writes group AR:APPLICATION-RECORD-ELEMENT
        Type: Abstract
        """
        if elem.is_optional is not None:
            self._add_content('IS-OPTIONAL', self._format_boolean(elem.is_optional))

    def _write_application_array_data_type(self, elem: ar_element.ApplicationArrayDataType) -> None:
        """
        Writes complex type AR:APPLICATION-ARRAY-DATA-TYPE
        Type: Concrete
        Tag variants: 'APPLICATION-ARRAY-DATA-TYPE'
        """
        assert isinstance(elem, ar_element.ApplicationArrayDataType)
        self._add_child("APPLICATION-ARRAY-DATA-TYPE")
        self._write_referrable(elem)
        self._write_multilanguage_referrable(elem)
        self._write_identifiable(elem)
        self._write_autosar_data_type(elem)
        self._write_application_array_data_type_group(elem)
        self._leave_child()

    def _write_application_array_data_type_group(self, elem: ar_element.ApplicationArrayDataType) -> None:
        """
        Writes group AR:APPLICATION-ARRAY-DATA-TYPE
        Type: Abstract
        """
        if elem.dynamic_array_size_profile is not None:
            self._add_content("DYNAMIC-ARRAY-SIZE-PROFILE", str(elem.dynamic_array_size_profile))
        if elem.element is not None:
            self._write_application_array_element(elem.element)

    def _write_application_record_data_type(self, elem: ar_element.ApplicationRecordDataType) -> None:
        """
        Writes complex type AR:APPLICATION-RECORD-DATA-TYPE
        Type: Concrete
        Tag variants: 'APPLICATION-RECORD-DATA-TYPE'
        """
        assert isinstance(elem, ar_element.ApplicationRecordDataType)
        self._add_child("APPLICATION-RECORD-DATA-TYPE")
        self._write_referrable(elem)
        self._write_multilanguage_referrable(elem)
        self._write_identifiable(elem)
        self._write_autosar_data_type(elem)
        self._write_application_record_data_type_group(elem)
        self._leave_child()

    def _write_application_record_data_type_group(self, elem: ar_element.ApplicationRecordDataType) -> None:
        """
        Writes group AR:APPLICATION-RECORD-DATA-TYPE
        Type: Abstract
        """
        if len(elem.elements) > 0:
            self._add_child("ELEMENTS")
            for child_elem in elem.elements:
                self._write_application_record_element(child_elem)
            self._leave_child()

    def _write_data_type_map(self, elem: ar_element.DataTypeMap) -> None:
        """
        Writes DataTypeMap
        Type: Concrete
        Tag variants: 'DATA-TYPE-MAP'
        """
        assert isinstance(elem, ar_element.DataTypeMap)
        self._add_child("DATA-TYPE-MAP")
        if elem.appl_data_type_ref is not None:
            self._write_application_data_type_ref(elem.appl_data_type_ref, "APPLICATION-DATA-TYPE-REF")
        if elem.impl_data_type_ref is not None:
            self._write_impl_data_type_ref(elem.impl_data_type_ref)
        self._leave_child()

    def _write_data_type_mapping_set(self, elem: ar_element.DataTypeMappingSet) -> None:
        """
        Writes DataTypeMappingSet
        Type: Concrete
        Tag variants: 'DATA-TYPE-MAPPING-SET'
        """
        assert isinstance(elem, ar_element.DataTypeMappingSet)
        attr: TupleList = []
        self._collect_identifiable_attributes(elem, attr)
        self._add_child("DATA-TYPE-MAPPING-SET", attr)
        self._write_referrable(elem)
        self._write_multilanguage_referrable(elem)
        self._write_identifiable(elem)
        if len(elem.data_type_maps) > 0:
            self._add_child("DATA-TYPE-MAPS")
            for child_elem in elem.data_type_maps:
                self._write_data_type_map(child_elem)
            self._leave_child()
        # .MODE-REQUEST-TYPE-MAPS not yet implemented
        self._leave_child()

    def _write_value_list(self, elem: ar_element.ValueList) -> None:
        """
        Writes complex-type AR:VALUE-LIST
        Type: Concrete
        Tag variants: 'SW-ARRAYSIZE'
        """
        assert isinstance(elem, ar_element.ValueList)
        tag = "SW-ARRAYSIZE"
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            self._write_value_list_group(elem)
            self._leave_child()

    def _write_value_list_group(self, elem: ar_element.SwValues) -> None:
        """
        Writes group AR:VALUE-LIST
        Type: abstract
        """
        for value in elem.values:
            content = self._format_number(value)
            self._add_content("V", content)

    # Reference Elements

    def _collect_base_ref_attr(self,
                               elem: ar_element.BaseRef,
                               attr: TupleList) -> None:
        attr.append(('DEST', ar_enum.enum_to_xml(elem.dest)))

    def _write_compu_method_ref(self, elem: ar_element.CompuMethodRef) -> None:
        """
        Writes complex type AR:COMPU-METHOD-REF
        Type: Concrete
        Tag variants: 'COMPU-METHOD-REF'

        Note: The name of the complex-type is anonymous in the XML schema.

        """
        assert isinstance(elem, ar_element.CompuMethodRef)
        attr: TupleList = []
        self._collect_base_ref_attr(elem, attr)
        self._add_content('COMPU-METHOD-REF', elem.value, attr)

    def _write_data_constraint_ref(self, elem: ar_element.DataConstraintRef) -> None:
        """
        Writes complex type AR:DATA-CONSTR-REF
        Type: Concrete
        Tag variants: 'DATA-CONSTR-REF'

        Note: The name of the complex-type is anonymous in the XML schema.

        """
        assert isinstance(elem, ar_element.DataConstraintRef)
        attr: TupleList = []
        self._collect_base_ref_attr(elem, attr)
        self._add_content('DATA-CONSTR-REF', elem.value, attr)

    def _write_function_ptr_signature_ref(self, elem: ar_element.FunctionPtrSignatureRef) -> None:
        """
        Writes complex type AR:FunctionPtrSignatureRef
        Type: Concrete
        Tag variants: 'FunctionPtrSignatureRef'

        Note: The name of the complex-type is anonymous in the XML schema.

        """
        assert isinstance(elem, ar_element.FunctionPtrSignatureRef)
        attr: TupleList = []
        self._collect_base_ref_attr(elem, attr)
        self._add_content('FUNCTION-POINTER-SIGNATURE-REF', elem.value, attr)

    def _write_impl_data_type_ref(self, elem: ar_element.ImplementationDataTypeRef) -> None:
        """
        Writes complex type AR:IMPLEMENTATION-DATA-TYPE-REF
        Type: Concrete
        Tag variants: 'IMPLEMENTATION-DATA-TYPE-REF'

        Note: The name of the complex-type is anonymous in the XML schema.

        """
        assert isinstance(elem, ar_element.ImplementationDataTypeRef)
        attr: TupleList = []
        self._collect_base_ref_attr(elem, attr)
        self._add_content('IMPLEMENTATION-DATA-TYPE-REF', elem.value, attr)

    def _write_sw_base_type_ref(self, elem: ar_element.SwBaseTypeRef) -> None:
        """
        Writes complex type AR:SW-BASE-TYPE-REF
        Type: Concrete
        Tag variants: 'BASE-TYPE-REF'

        Note: The name of the complex-type is anonymous in the XML schema.

        """
        assert isinstance(elem, ar_element.SwBaseTypeRef)
        attr: TupleList = []
        self._collect_base_ref_attr(elem, attr)
        self._add_content('BASE-TYPE-REF', elem.value, attr)

    def _write_sw_addr_method_ref(self, elem: ar_element.SwAddrMethodRef) -> None:
        """
        Writes complex type AR:SW-ADDR-METHOD-REF
        Type: Concrete
        Tag variants: 'SW-ADDR-METHOD-REF'
        """
        assert isinstance(elem, ar_element.SwAddrMethodRef)
        attr: TupleList = []
        self._collect_base_ref_attr(elem, attr)
        self._add_content('SW-ADDR-METHOD-REF', elem.value, attr)

    def _write_unit_ref(self, elem: ar_element.UnitRef) -> None:
        """
        Writes complex type AR:UNIT-REF
        Type: Concrete
        Tag variants: 'UNIT-REF'
        """
        assert isinstance(elem, ar_element.UnitRef)
        attr: TupleList = []
        self._collect_base_ref_attr(elem, attr)
        self._add_content('UNIT-REF', elem.value, attr)

    def _write_physical_dimension_ref(self, elem: ar_element.PhysicalDimensionRef) -> None:
        """
        Writes PHYSICAL-DIMENSION-REF
        Type: Concrete
        Tag variants: 'PHYSICAL-DIMENSION-REF'
        """
        assert isinstance(elem, ar_element.PhysicalDimensionRef)
        attr: TupleList = []
        self._collect_base_ref_attr(elem, attr)
        self._add_content('PHYSICAL-DIMENSION-REF', elem.value, attr)

    def _write_index_data_type_ref(self, elem: ar_element.IndexDataTypeRef) -> None:
        """
        Writes reference to IndexDataType
        Type: Concrete
        Tag variants: 'INDEX-DATA-TYPE-REF'
        """
        assert isinstance(elem, ar_element.IndexDataTypeRef)
        attr: TupleList = []
        self._collect_base_ref_attr(elem, attr)
        self._add_content('INDEX-DATA-TYPE-REF', elem.value, attr)

    def _write_application_data_type_ref(self, elem: ar_element.ApplicationDataTypeRef, tag: str) -> None:
        """
        Writes reference to ApplicationDataType
        Type: Concrete
        Tag variants: 'TYPE-TREF', 'APPLICATION-DATA-TYPE-REF'
        """
        assert isinstance(elem, ar_element.ApplicationDataTypeRef)
        attr: TupleList = []
        self._collect_base_ref_attr(elem, attr)
        self._add_content(tag, elem.value, attr)

    def _write_constant_ref(self, elem: ar_element.ApplicationDataTypeRef, tag: str) -> None:
        """
        Writes reference to ConstantSpecification
        Type: Concrete
        Tag variants: 'CONSTANT-REF'

        Don't confuse this with the ConstantReference class.
        """
        assert isinstance(elem, ar_element.ConstantRef)
        attr: TupleList = []
        self._collect_base_ref_attr(elem, attr)
        self._add_content(tag, elem.value, attr)

# Constant and value specifications

    def _write_text_value_specification(self, elem: ar_element.TextValueSpecification) -> None:
        """
        Writes AR:TEXT-VALUE-SPECIFICATION
        Type: Concrete
        Tag variants: 'TEXT-VALUE-SPECIFICATION'
        """
        assert isinstance(elem, ar_element.TextValueSpecification)
        tag = "TEXT-VALUE-SPECIFICATION"
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            self._write_value_specification_group(elem)
            if elem.value is not None:
                self._add_content("VALUE", str(elem.value))
            self._leave_child()

    def _write_numerical_value_specification(self, elem: ar_element.NumericalValueSpecification) -> None:
        """
        Writes AR:NUMERICAL-VALUE-SPECIFICATION
        Type: Concrete
        Tag variants: 'NUMERICAL-VALUE-SPECIFICATION'
        """
        assert isinstance(elem, ar_element.NumericalValueSpecification)
        tag = "NUMERICAL-VALUE-SPECIFICATION"
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            self._write_value_specification_group(elem)
            if elem.value is not None:
                self._add_content("VALUE", self._format_number(elem.value))
            self._leave_child()

    def _write_not_available_value_specification(self, elem: ar_element.NotAvailableValueSpecification) -> None:
        """
        Writes AR:NOT-AVAILABLE-VALUE-SPECIFICATION
        Type: Concrete
        Tag variants: 'NOT-AVAILABLE-VALUE-SPECIFICATION'
        """
        assert isinstance(elem, ar_element.NotAvailableValueSpecification)
        tag = "NOT-AVAILABLE-VALUE-SPECIFICATION"
        if elem.is_empty_with_ignore({"default_pattern_format"}):
            self._add_content(tag)
        else:
            self._add_child(tag)
            self._write_value_specification_group(elem)
            if elem.default_pattern is not None:
                self._add_content("DEFAULT-PATTERN", str(elem.default_pattern))  # TODO support numerical formats
            self._leave_child()

    def _write_array_value_specification(self, elem: ar_element.ArrayValueSpecification) -> None:
        """
        Writes complex-type AR:ARRAY-VALUE-SPECIFICATION
        Type: Concrete
        Tag variants: 'ARRAY-VALUE-SPECIFICATION'
        """
        assert isinstance(elem, ar_element.ArrayValueSpecification)
        tag = "ARRAY-VALUE-SPECIFICATION"
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            self._write_value_specification_group(elem)
            self._write_array_value_specification_group(elem)
            self._leave_child()

    def _write_array_value_specification_group(self, elem: ar_element.ArrayValueSpecification) -> None:
        """
        Writes group AR:ARRAY-VALUE-SPECIFICATION
        Type: Abstract
        """
        if elem.elements:
            self._add_child("ELEMENTS")
            for child_element in elem.elements:
                self._write_value_specification_element(child_element)
            self._leave_child()

    def _write_record_value_specification(self, elem: ar_element.RecordValueSpecification) -> None:
        """
        Writes complex-type AR:RECORD-VALUE-SPECIFICATION
        Type: Concrete
        Tag variants: 'RECORD-VALUE-SPECIFICATION'
        """
        assert isinstance(elem, ar_element.RecordValueSpecification)
        tag = "RECORD-VALUE-SPECIFICATION"
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            self._write_value_specification_group(elem)
            self._write_record_value_specification_group(elem)
            self._leave_child()

    def _write_record_value_specification_group(self, elem: ar_element.RecordValueSpecification) -> None:
        """
        Writes group AR:RECORD-VALUE-SPECIFICATION
        Type: Abstract
        """
        if elem.fields:
            self._add_child("FIELDS")
            for field in elem.fields:
                self._write_value_specification_element(field)
            self._leave_child()

    def _write_application_value_specification(self, elem: ar_element.ApplicationValueSpecification) -> None:
        """
        Writes complex-type AR:APPLICATION-VALUE-SPECIFICATION
        """
        assert isinstance(elem, ar_element.ApplicationValueSpecification)
        tag = "APPLICATION-VALUE-SPECIFICATION"
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            self._write_value_specification_group(elem)
            self._write_application_specification_group(elem)
            self._leave_child()

    def _write_application_specification_group(self, elem: ar_element.ApplicationValueSpecification) -> None:
        """
        Writes group AR:APPLICATION-VALUE-SPECIFICATION
        """
        if elem.category is not None:
            self._add_content("CATEGORY", str(elem.category))
        if elem.sw_axis_conts:
            self._add_child("SW-AXIS-CONTS")
            for child in elem.sw_axis_conts:
                self._write_sw_axis_cont(child)
            self._leave_child()
        if elem.sw_value_cont is not None:
            self._write_sw_value_cont(elem.sw_value_cont)

    def _write_value_specification_group(self, elem: ar_element.ValueSpecification) -> None:
        """
        Writes group AR:VALUE-SPECIFICATION
        Type: Abstract
        """
        if elem.label is not None:
            self._add_content("SHORT-LABEL", str(elem.label))

    def _write_value_specification_element(self, elem: ValueSpeficationElement) -> None:
        """
        Switched writer for value specification elements
        """
        class_name = elem.__class__.__name__
        write_method = self.switcher_value_specification.get(class_name, None)
        if write_method is not None:
            write_method(elem)
        else:
            raise NotImplementedError(f"Found no writer for class {class_name}")

    def _write_constant_specification(self, elem: ar_element.ConstantSpecification) -> None:
        """
        Writes complex type AR:CONSTANT-SPECIFICATION
        """
        assert isinstance(elem, ar_element.ConstantSpecification)
        attr: TupleList = []
        self._collect_identifiable_attributes(elem, attr)
        self._add_child('CONSTANT-SPECIFICATION', attr)
        self._write_referrable(elem)
        self._write_multilanguage_referrable(elem)
        self._write_identifiable(elem)
        self._write_constant_specification_group(elem)
        self._leave_child()

    def _write_constant_specification_group(self, elem: ar_element.ConstantSpecification) -> None:
        """
        Writes group AR:CONSTANT-SPECIFICATION
        """
        if elem.value is not None:
            self._add_child("VALUE-SPEC")
            self._write_value_specification_element(elem.value)
            self._leave_child()

    def _write_constant_reference(self, elem: ar_element.ConstantReference) -> None:
        """
        Writes complex type AR:CONSTANT-REFERENCE
        """
        assert isinstance(elem, ar_element.ConstantReference)
        tag = "CONSTANT-REFERENCE"
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            self._write_value_specification_group(elem)
            if elem.constant_ref is not None:
                self._write_constant_ref(elem.constant_ref, "CONSTANT-REF")
            self._leave_child()

# CalibrationData elements

    def _write_sw_values(self, elem: ar_element.SwValues) -> None:
        """
        Writes complex-type AR:SW-VALUES
        Type: Concrete
        Tag variants: 'SW-VALUES-PHYS'
        """
        assert isinstance(elem, ar_element.SwValues)
        tag = "SW-VALUES-PHYS"
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            self._write_sw_values_group(elem)
            self._leave_child()

    def _write_sw_values_group(self, elem: ar_element.SwValues) -> None:
        """
        Writes group AR:SW-VALUES (also used part of AR:VALUE-GROUP)
        Type: abstract
        """
        for value in elem.values:
            if isinstance(value, str):
                self._add_content("VT", value)
            elif isinstance(value, (int, float, ar_element.NumericalValue)):
                self._add_content("V", self._format_number(value))
            elif isinstance(value, ar_element.ValueGroup):
                self._write_value_group(value, "VG")
            else:
                raise NotImplementedError(str(type(value)))

    def _write_value_group(self, elem: ar_element.ValueGroup, tag: str) -> None:
        """
        Writes complex-type AR:VALUE-GROUP
        Type: Concrete
        """
        assert isinstance(elem, ar_element.ValueGroup)
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            if elem.label is not None:
                self._write_multi_language_long_name(elem.label, "LABEL")
            self._write_sw_values_group(elem)
            self._leave_child()

    def _write_sw_axis_cont(self, elem: ar_element.SwAxisCont) -> None:
        """
        Writes Complex-type SW-AXIS-CONT
        Type: Concrete
        """
        assert isinstance(elem, ar_element.SwAxisCont)
        tag = "SW-AXIS-CONT"
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            self._write_sw_axis_cont_group(elem)
            self._leave_child()

    def _write_sw_axis_cont_group(self, elem: ar_element.SwAxisCont) -> None:
        """
        Writes group SW-AXIS-CONT
        Type: Concrete
        """
        if elem.category is not None:
            self._add_content("CATEGORY", ar_enum.enum_to_xml(elem.category))
        if elem.unit_ref is not None:
            self._write_unit_ref(elem.unit_ref)
        if elem.unit_display_name is not None:
            self._write_single_language_unit_names(elem.unit_display_name, "UNIT-DISPLAY-NAME")
        if elem.sw_axis_index is not None:
            self._add_content("SW-AXIS-INDEX", str(elem.sw_axis_index))
        if elem.sw_array_size is not None:
            self._write_value_list(elem.sw_array_size)
        if elem.sw_values_phys is not None:
            self._write_sw_values(elem.sw_values_phys)

    def _write_sw_value_cont(self, elem: ar_element.SwValueCont) -> None:
        """
        Writes Complex-type SW-VALUE-CONT
        Type: Concrete
        """
        assert isinstance(elem, ar_element.SwValueCont)
        tag = "SW-VALUE-CONT"
        if elem.is_empty:
            self._add_content(tag)
        else:
            self._add_child(tag)
            self._write_sw_value_cont_group(elem)
            self._leave_child()

    def _write_sw_value_cont_group(self, elem: ar_element.SwValueCont) -> None:
        """
        Writes group SW-VALUE-CONT
        Type: Concrete
        """
        if elem.unit_ref is not None:
            self._write_unit_ref(elem.unit_ref)
        if elem.unit_display_name is not None:
            self._write_single_language_unit_names(elem.unit_display_name, "UNIT-DISPLAY-NAME")
        if elem.sw_array_size is not None:
            self._write_value_list(elem.sw_array_size)
        if elem.sw_values_phys is not None:
            self._write_sw_values(elem.sw_values_phys)
