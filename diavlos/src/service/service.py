"""A module for fetching, adding and updating services."""
import logging
import mwclient
import re

from time import mktime
from datetime import datetime

from mwtemplates import TemplateEditor

from .error import ServiceErrorCode as ErrorCode
from diavlos.src.bpmn import BPMN
from diavlos.src.site import Site
from diavlos.src.site import SiteError

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    """ServiceError exception"""


def _error(message):
    logger.error(message)
    raise ServiceError(message)


def _template_text(template_name, template_instance):
    template_text = template_name
    for field_name, field_value in template_instance.items():
        template_text += f'\n |{field_name}={field_value}'
    return f'{{{{{template_text}\n}}}}\n'


class Service:
    TITLE_KEY= 'process_official_title'
    NAME_KEY = 'name'
    FULL_NAME_KEY = 'fullname'
    FIELDS_KEY = 'fields'
    UPDATE_KEY = 'update'
    PAGE_ID_KEY = 'page_id'
    PUBLISHED_NAMESPACE = 'ΔΔ'
    BEING_EDITTED_NAMESPACE = 'ΥΕ'
    TO_BE_APPROVED_NAMESPACE = 'ΠΕ'
    TO_BE_PUBLISHED_NAMESPACE = 'ΠΔ'
    NAMESPACES = [
        PUBLISHED_NAMESPACE,
        BEING_EDITTED_NAMESPACE,
        TO_BE_APPROVED_NAMESPACE,
        TO_BE_PUBLISHED_NAMESPACE
    ]
    DEFAULT_NAMESPACE = BEING_EDITTED_NAMESPACE
    DEFAULT_NAMESPACE_PREFIX = f'{DEFAULT_NAMESPACE}:'
    REGEX_HAS_NAMESPACE_PREFIX = re.compile(
        rf'^(?:{PUBLISHED_NAMESPACE}|{BEING_EDITTED_NAMESPACE}|'
        rf'{TO_BE_APPROVED_NAMESPACE}|{TO_BE_PUBLISHED_NAMESPACE}):')
    CATEGORY_NAME = 'Κατάλογος Διαδικασιών'
    CATEGORY = f'Category:{CATEGORY_NAME}'
    TEMPLATE_NAME = 'Process'
    UUID_PROPERTY_NAME = 'Process_uuid'
    ID_PROPERTY_NAME = 'Process_id'
    BPMN_PATH = 'BPMN'

    def __init__(self, site=None):
        self._site = site or Site()

    def set_site(self, site):
        if site is not self._site:
            self._site = site

    def _has_namespace_prefix(self, string):
        return bool(re.match(self.REGEX_HAS_NAMESPACE_PREFIX, string))

    def _service_dict(self, name, full_name, update_date, page_id, template_editor):
        dict_ = {
            self.NAME_KEY: name,
            self.FULL_NAME_KEY: full_name,
            self.UPDATE_KEY: update_date,
            self.PAGE_ID_KEY: page_id,
            self.FIELDS_KEY: {}
        }
        fields_dict = dict_[self.FIELDS_KEY]
        for tpl_name in template_editor.templates.keys():
            tpl_instances = template_editor.templates[tpl_name]
            tpl_instances_data = {}
            for tpl_idx, tpl_instance in enumerate(tpl_instances):
                tpl_instance_dict = {}
                for param in tpl_instance.parameters:
                    tpl_instance_dict[param.name] = param.value
                tpl_instances_data[tpl_idx + 1] = tpl_instance_dict
            fields_dict[tpl_name] = tpl_instances_data
        return dict_

    def _page_name(self, name):
        if not self._has_namespace_prefix(name):
            return f'{self.DEFAULT_NAMESPACE_PREFIX}{name}'
        return name

    def _page(self, name):
        if self._has_namespace_prefix(name):
            page = self._site.pages(name)
            return page, page.exists
        name = self._page_name(name)
        page = self._site.pages(name)
        page_exists = page.exists
        if page_exists:
            return page, page_exists
        split_name = name.split(':')
        ns = split_name[0]
        title = split_name[1]
        other_namespaces = [
            other_ns for other_ns in self.NAMESPACES if other_ns != ns]
        for other_ns in other_namespaces:
            other_ns_name = f'{other_ns}:{title}'
            other_ns_page = self._site.pages(other_ns_name)
            other_ns_page_exists = other_ns_page.exists
            if other_ns_page_exists:
                return other_ns_page, other_ns_page_exists
        return page, page_exists

    def _id_by_fullname(self,name_):
        property_name = self.TITLE_KEY
        askargs_conditions = f'{property_name}::{name_[3:]}'
        try:
            site_response = self._site.get(
                'askargs', format='json',
                conditions=askargs_conditions,
                printouts="process_id|process_uuid")
        except mwclient.errors.APIError:
            result = ErrorCode.SITE_API_ERROR
        else:
            site_response_results = site_response['query']['results']
            if len(site_response_results) >= 1:
                result = site_response['query']['results'][name_]['printouts']['process_id']
            else:
                result = None

        return result

    def _name_by_id(self, id_, is_uuid=False):
        property_name = self.UUID_PROPERTY_NAME \
            if is_uuid else self.ID_PROPERTY_NAME

        id_str = str(id_)
        zero_filled_id = id_str.zfill(6)

        askargs_conditions = f'{property_name}::{zero_filled_id}'
        try:
            site_response = self._site.get(
                'askargs', format='json',
                conditions=askargs_conditions)
        except mwclient.errors.APIError:
            result = ErrorCode.SITE_API_ERROR
        else:
            site_response_results = site_response['query']['results']
            if len(site_response_results) >= 1:
                result = next(iter(site_response_results))
            else:
                result = None
        return result

    def site_auto_login(self):
        """Do an automatic site login."""
        try:
            self._site.login(auto=True)
        except SiteError as e:
            _error(str(e))

    def fetch_all(self, include_info=False, page_continue='', limit=10):
        """Fetch all services.

        Args:
            limit (int): The max number of services to return (mediawiki
                parameter).
            page_continue (string): A pagination string for accessing the
                next result page (mediawiki parameter).
            include_info (bool): Whether to fetch all information for each
                service or just their names.

        Returns:
            dict: The services to return.
        """
        try:
            mw_response = self._site.get('query', format='json',
                                         list='categorymembers',
                                         cmtitle=self.CATEGORY,
                                         cmcontinue=page_continue,
                                         cmlimit=limit)
        except mwclient.errors.APIError:
            result = ErrorCode.SITE_API_ERROR
        else:
            if 'continue' in mw_response:
                continue_response = mw_response['continue']['cmcontinue']
            else:
                continue_response = None
            if include_info:
                services_data = [{
                    "name":category_member['title'].replace(
                        self.DEFAULT_NAMESPACE_PREFIX, ''),
                    "info":self.fetch_by_name(category_member['title'])}
                    for category_member in mw_response['query'][
                        'categorymembers']
                ]
            else:
                services_data = [{
                    "name":category_member['title'].replace(
                        self.DEFAULT_NAMESPACE_PREFIX, ''),
                    "id":self.get_id_by_fullname(category_member['title'])}
                    for category_member in mw_response['query'][
                        'categorymembers']
                ]
            result = {
                'page_continue': continue_response,
                'services': services_data
            }
        return result
    
    def get_id_by_fullname(self,name):
        """Get the process id by fullname.
        Args:
            name (string): The name of the service.
        Returns:
            string: or None if the attribute is not yet set.
        """
        id = self._id_by_fullname(name)
        if id != None :
           if len(id) == 1:
              id= id[0]
           else :
              id = None   
        return id

    def fetch_by_name(self, name, fetch_bpmn_digital_steps=None):
        """Fetch a service by name.

        Args:
            name (string): The name of the service.
            fetch_bpmn_digital_steps (bool): Whether to fetch digital or
                manual bpmn data. If None, do not return bpmn data.
                Default: None.

        Returns:
            :obj:`enum 'ServiceErrorCode'`: A ServiceErrorCode.NOT_FOUND
                enum, if the service is not found,
            dict: service information if `fetch_bpmn_digital_steps` is None,
            string: otherwise, the BPMN XML of the service.
        """
        self._site.login(auto=True)
        page, page_exists = self._page(name)
        if page_exists:
            page = page.resolve_redirect()
            page_name = page.page_title
            page_full_name = page.name
            current_revision = page.revisions(limit=1,dir='older').next()
            latest_update_date=datetime.utcfromtimestamp(mktime(current_revision['timestamp'])).isoformat()
            page_id=page._info['pageid']
            service_dict = self._service_dict(page_name, page_full_name, latest_update_date, page_id, TemplateEditor(page.text()))
            if fetch_bpmn_digital_steps is None:
                data = service_dict
            else:
                data = BPMN(
                    digital_steps=fetch_bpmn_digital_steps).xml(
                    service_dict).replace('\n', '').replace(
                    '\t', '').replace('\"', '\'')
            result = data
        else:
            result = ErrorCode.NOT_FOUND
        return result

    def fetch_by_id(self, id_, is_uuid=False,
                    fetch_bpmn_digital_steps=None):
        """Fetch a service by id.

        Args:
            id_ (string or int): The id of the service.
            is_uuid (bool): Whether `id_` is the service id or uuid.
            fetch_bpmn_digital_steps (bool): Whether to fetch digital or
                manual bpmn data. If None, do not return bpmn data.
                Default: None.

        Returns:
            :obj:`enum 'ServiceErrorCode'`: A ServiceErrorCode.NOT_FOUND
                enum, if the service is not found,
            dict: the service information if fetch_bpmn_digital_steps is None,
            string: otherwise, the BPMN XML of the service.
        """
        service_name = self._name_by_id(id_, is_uuid=is_uuid)
        if service_name is None:
            result = ErrorCode.NOT_FOUND
        else:
            result = self.fetch_by_name(
                service_name,
                fetch_bpmn_digital_steps=fetch_bpmn_digital_steps)
        return result

    def update_by_id(self, id_, fields, is_uuid=False):
        """Update a service by id.

        Args:
            id_ (string or int): The id of the service.
            fields (dict): The service fields to update.
            is_uuid (bool): Whether `id_` is the service id or uuid.

        Returns:
            :obj:`enum 'ServiceErrorCode'`: A ServiceErrorCode enum for cases
                such as if the service was not found, etc.
            dict: the service information if fetch_bpmn_digital_steps is None,
        """
        service_name = self._name_by_id(id_, is_uuid=is_uuid)
        if service_name is None:
            result = ErrorCode.NOT_FOUND
        else:
            result = self.update(service_name, fields)
        return result

    def update(self, name, fields):
        """Update a service.

        Args:
            name (string): The name of the service.
            fields (dict): The service fields to update.

        Returns:
            :obj:`enum 'ServiceErrorCode'`: A ServiceErrorCode enum for cases
                such as if the service was not found, etc.
            dict: the service information if fetch_bpmn_digital_steps is None,
        """
        page, page_exists = self._page(name)
        if not page.can('edit'):
            result = ErrorCode.UNAUTHORIZED_ACTION
        elif page_exists:
            te = TemplateEditor(page.text())
            fields_updated = False
            for tpl_name, tpl_instances in fields.items():
                template_names = [tpl.lower() for tpl in te.templates.keys()]
                if tpl_name in template_names:
                    page_tpl_instances = te.templates[tpl_name]
                    # Update template instances
                    for instance_num_str, tpl_instance in \
                            tpl_instances.items():
                        if not instance_num_str.isdigit():
                            break
                        instance_num = int(instance_num_str)
                        try:
                            page_tpl = page_tpl_instances[instance_num - 1]
                        except IndexError:
                            # Template instance does not exist, create it
                            if instance_num > len(page_tpl_instances):
                                # Only if numbering is greater than the last
                                # existing instance number
                                new_tpl_text = _template_text(
                                    tpl_name, tpl_instance)
                                if new_tpl_text:
                                    new_wiki_text = ''
                                    for name, tpls in te.templates.items():
                                        for tpl in tpls:
                                            new_wiki_text += f'{str(tpl)}\n'
                                        if name.lower() == tpl_name:
                                            new_wiki_text += \
                                                f'{new_tpl_text}'
                                    if new_wiki_text:
                                        te = TemplateEditor(new_wiki_text)
                                        if not fields_updated:
                                            fields_updated = True
                        else:
                            for field_name, field_value in \
                                    tpl_instance.items():
                                # Update or create field
                                page_tpl.parameters[field_name] = \
                                    field_value
                                if not fields_updated:
                                    fields_updated = True
                else:
                    new_templates_text = ''
                    for instance_num_str, tpl_instance in \
                            tpl_instances.items():
                        new_templates_text += _template_text(
                            tpl_name, tpl_instance)
                    if new_templates_text:
                        # Append new templates to wiki text
                        new_wiki_text = \
                            f'{te.wikitext()}\n{new_templates_text}'
                        te = TemplateEditor(new_wiki_text)
                        if not fields_updated:
                            fields_updated = True
            if fields_updated:
                wikitext = te.wikitext().replace('\n\n', '\n')
                if wikitext[0] == '\n':
                    wikitext = wikitext[1:]
                page.edit(wikitext)
                page_name = page.page_title
                page_full_name = page.name
                current_revision = page.revisions(limit=1,dir='older').next()
                latest_update_date=datetime.utcfromtimestamp(mktime(current_revision['timestamp'])).isoformat()
                page_id=page._info['pageid']
                result = self._service_dict(page_name, page_full_name, latest_update_date, page_id, TemplateEditor(page.text()))
            else:
                result = ErrorCode.NO_FIELD_UPDATED
        else:
            result = ErrorCode.NOT_FOUND
        return result

    def add(self, name, fields):
        """Add a service.

        Args:
            name (string): The name of the service.
            fields (dict): The service fields to add.

        Returns:
            :obj:`enum 'ServiceErrorCode'`: A ServiceErrorCode enum for cases
                such as if the service already exists, etc.
            dict: the service information if fetch_bpmn_digital_steps is None,
        """
        page, page_exists = self._page(name)
        if page_exists:
            result = ErrorCode.ALREADY_EXISTS
        elif not page.can('edit'):
            result = ErrorCode.UNAUTHORIZED_ACTION
        else:
            templates_text = ''
            for tpl_name, tpl_instances in fields.items():
                for tpl_instance in tpl_instances:
                    templates_text += _template_text(tpl_name, tpl_instance)
            te = TemplateEditor(templates_text)
            if te.templates:
                page.edit(te.wikitext())
                page_name = page.page_title
                page_full_name = page.name
                current_revision = page.revisions(limit=1,dir='older').next()
                latest_update_date=datetime.utcfromtimestamp(mktime(current_revision['timestamp'])).isoformat()
                page_id=page._info['pageid']               
                result = self._service_dict(page_name, page_full_name, latest_update_date, page_id, te)
            else:
                result = ErrorCode.INVALID_TEMPLATE
        return result
