# transport/admin.py

from django.contrib import admin
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from .models import TransportLoad, DeliverySite
from commercial.models import Client
from decimal import Decimal
from foodlinecontrol.admin_base import ArchivableAdmin
from tenants.admin_utils import SiteAwareModelAdmin

def _render_date_group(production_date, batch_rows):
    """Render a group of batches with same production date using rowspan."""
    from django.urls import reverse
    from manufacturing.models import Production
    from datetime import datetime
    
    html = ""
    rowspan = len(batch_rows)
    
    production_link = production_date
    if production_date and production_date != "-":
        try:
            date_obj = datetime.strptime(production_date, "%d/%m/%Y").date()
            production = Production.objects.filter(production_date=date_obj).first()
            
            if production:
                url = reverse('admin:manufacturing_production_change', args=[production.pk])
                production_link = f'<a href="{url}" style="color:#417690; text-decoration:none;">{production_date}</a>'
        except (ValueError, Production.DoesNotExist):
            pass
    
    for i, batch in enumerate(batch_rows):
        html += '<tr style="border-bottom:1px solid #ddd;">'
        
        if i == 0:
            html += f'<td style="padding:8px; vertical-align:middle; font-weight:bold;" rowspan="{rowspan}">{production_link}</td>'
        
        html += f'<td style="padding:8px;">{escape(batch.get("batch_number", "-"))}</td>'
        html += f'<td style="padding:8px;">{escape(batch.get("product", "-"))}</td>'
        html += f'<td style="padding:8px;">{escape(batch.get("size", "-"))}</td>'
        html += f'<td style="padding:8px; text-align:right;">{batch.get("qty_for_invoice", 0):.0f}</td>'
        html += '</tr>'
    
    return html


@admin.register(TransportLoad)
class TransportLoadAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    
    list_display = [
        'load_number',
        'client',
        'delivery_institution',
        'batch_summary_display',
        'billing_date',
        'released_date',
        'transporter',
    ]
    
    list_filter = [
        'released_date',
        'billing_date',
        'transporter',
        'client',
    ]
    
    search_fields = [
        'load_number',
        'billing_document__base_number',
        'client__name',
    ]
    
    readonly_fields = [
        'client',
        'delivery_institution',
        'billing_date',
        'released_date',
        'load_total_display',
        'batch_data_display',
        'billing_document_link',
        'transporter',
        'documents_table_display',
    ]
    
    fieldsets = (
        ("Information", {
            'fields': (
                ('load_number', 'client', 'delivery_institution'),
                ('billing_document_link', 'billing_date', 'released_date'),
            ),
        }),
        ("Transport", {
            'fields': (
                ('transporter', 'load_total_display'),
            ),
        }),
        ("Batch Details", {
            'fields': (
                'batch_data_display',
            ),
            'description': "Summary of batches included in this shipment"
        }),
            ("Documents", {
            'fields': (
                'documents_table_display',  
            ),
        }),
    )
    
    class Media:
        js = ('js/transport_documents.js',)
    
    def batch_summary_display(self, obj):
        if not obj.batch_data or not isinstance(obj.batch_data, list):
            return "-"
        
        count = len(obj.batch_data)
        batches = ", ".join([b.get('batch_number', '?') for b in obj.batch_data])
        return f"{count} batch{'es' if count != 1 else ''}: {batches}"
    
    batch_summary_display.short_description = "Batches"
    
    def documents_table_display(self, obj):
        """Display all documents in clean table format"""
        if not obj.pk:
            return "Save first"
        
        doc_types = [
            ('delivery_note', 'Delivery Note'),
            ('namra', 'NAMRA'),
            ('daff', 'DAFF'),
            ('meat_board', 'Meat Board'),
            ('import_permit', 'Import Permit'),
        ]
        
        html = '<table style="width: 100%; border-collapse: collapse;">'
        
        # Standard document types
        for doc_type, label in doc_types:
            docs = getattr(obj, f'{doc_type}_documents', [])
            
            html += '<tr style="border-bottom: 1px solid #e0e0e0;">'
            html += f'<td style="padding: 10px 20px 10px 0; width: 150px; font-weight: 500; vertical-align: top;">{label}</td>'
            html += '<td style="padding: 10px 0;">'
            
            html += f'<ul class="{doc_type}-doc-list" style="list-style: none; padding: 0; margin: 0 0 8px 0;">'
            
            for doc in docs:
                html += f'''
                <li class="{doc_type}-doc-item" style="display: inline-block; margin-right: 15px; margin-bottom: 5px;">
                    <a href="/media/{doc['file']}" target="_blank" style="color: #417690; font-size: 12px; text-decoration: none;">{doc['filename']}</a>
                    <button type="button"
                            class="{doc_type}-remove-row"
                            data-doc-id="{doc['id']}"
                            style="margin-left: 5px; border: none; background: none; color: #d32f2f; font-weight: bold; cursor: pointer; font-size: 16px; padding: 0; line-height: 1;">×</button>
                </li>
                '''
            
            html += '</ul>'
            html += f'<div class="{doc_type}-file-rows" style="display:none;"></div>'
            html += f'''
            <button type="button" 
                    class="{doc_type}-add-row" 
                    style="background: #417690; 
                           color: white; 
                           border: none; 
                           padding: 6px 16px; 
                           cursor: pointer; 
                           border-radius: 3px; 
                           font-size: 12px; 
                           font-weight: 500; 
                           white-space: nowrap; 
                           min-width: 70px;
                           display: inline-block;">
                + Add
            </button>
            '''
            
            html += '</td></tr>'
        
        # ✅ OTHER DOCUMENTS - dynamic rows
        other_docs = obj.other_documents if obj.other_documents else []

        for idx, doc_cat in enumerate(other_docs):
            cat_name = escape(doc_cat.get('name', 'Other'))
            files = doc_cat.get('files', [])
            
            html += '<tr style="border-bottom: 1px solid #e0e0e0;">'
            # ✅ LEFT COLUMN: Name + Remove button (matching JavaScript)
            html += f'''
            <td style="padding: 10px 20px 10px 0; width: 150px; font-weight: 500; vertical-align: top;">
                <div>{cat_name}</div>
                <button type="button" 
                        class="other-remove-category" 
                        data-idx="{idx}"
                        style="background: #d32f2f; 
                               color: white; 
                               border: none; 
                               padding: 8px 16px; 
                               cursor: pointer; 
                               border-radius: 3px; 
                               font-size: 13px; 
                               font-weight: 500;
                               margin-top: 8px;
                               margin-left: 10px;
                               display: block;
                               min-width: 80px;">
                    Remove
                </button>
            </td>
            '''
            # ✅ RIGHT COLUMN: Files + Add button
            html += '<td style="padding: 10px 0;">'
            
            html += f'<ul class="other-doc-list-{idx}" style="list-style: none; padding: 0; margin: 0 0 8px 0;">'
            
            for file in files:
                html += f'''
                <li class="other-doc-item" style="display: inline-block; margin-right: 15px; margin-bottom: 5px;">
                    <a href="/media/{escape(file['file'])}" target="_blank" style="color: #417690; font-size: 12px; text-decoration: none;">{escape(file['filename'])}</a>
                    <button type="button"
                            class="other-remove-file"
                            data-idx="{idx}"
                            data-file-id="{file['id']}"
                            style="margin-left: 5px; border: none; background: none; color: #d32f2f; font-weight: bold; cursor: pointer; font-size: 16px; padding: 0; line-height: 1;">×</button>
                </li>
                '''
            
            html += '</ul>'
            html += f'<div class="other-file-rows-{idx}" style="display:none;"></div>'
            html += f'''
            <button type="button" 
                    class="other-add-file" 
                    data-idx="{idx}"
                    style="background: #417690; 
                           color: white; 
                           border: none; 
                           padding: 6px 16px; 
                           cursor: pointer; 
                           border-radius: 3px; 
                           font-size: 12px; 
                           font-weight: 500; 
                           white-space: nowrap; 
                           min-width: 70px;
                           display: inline-block;">
                + Add
            </button>
            '''
            
            html += '</td>'
            html += '</tr>'
        
        # ✅ NEW DOCUMENT ROW - always visible
        html += '''
        <tr style="border-bottom: 1px solid #e0e0e0;">
            <td style="padding: 15px 20px 15px 0; width: 150px; vertical-align: middle;">
                <input type="text" 
                       id="new-doc-name" 
                       placeholder="Document name" 
                       style="width: 130px; padding: 8px; border: 1px solid #ccc; border-radius: 3px; font-size: 12px;">
            </td>
            <td style="padding: 15px 0;">
                <button type="button" 
                        id="add-new-document"
                        style="background: #417690; 
                               color: white; 
                               border: none; 
                               padding: 8px 20px; 
                               cursor: pointer; 
                               border-radius: 3px; 
                               font-size: 13px; 
                               font-weight: 500; 
                               white-space: nowrap; 
                               min-width: 120px;
                               display: inline-block;">
                    + Add
                </button>
            </td>
        </tr>
        '''
        
        html += '</table>'
        
        return mark_safe(html)

    documents_table_display.short_description = ""

    def batch_data_display(self, obj):
        if not obj.batch_data or not isinstance(obj.batch_data, list):
            return "No batch data"
        
        sorted_data = sorted(
            obj.batch_data,
            key=lambda x: x.get("production_date", "")
        )
        
        html = '<table style="width:100%; border-collapse:collapse; margin-top:10px;">'
        html += '<thead><tr style="background-color:#f5f5f5; border-bottom:2px solid #333;">'
        html += '<th style="padding:8px; text-align:left;">Production Date</th>'
        html += '<th style="padding:8px; text-align:left;">Batch Number</th>'
        html += '<th style="padding:8px; text-align:left;">Product</th>'
        html += '<th style="padding:8px; text-align:left;">Size</th>'
        html += '<th style="padding:8px; text-align:right;">Qty</th>'
        html += '</tr></thead>'
        html += '<tbody>'
        
        current_date = None
        date_group_rows = []
        
        for i, batch in enumerate(sorted_data):
            prod_date = batch.get("production_date", "-")
            
            if prod_date != current_date:
                if date_group_rows:
                    html += _render_date_group(current_date, date_group_rows)
                
                current_date = prod_date
                date_group_rows = [batch]
            else:
                date_group_rows.append(batch)
        
        if date_group_rows:
            html += _render_date_group(current_date, date_group_rows)
        
        html += '</tbody></table>'
        
        return mark_safe(html)

    batch_data_display.short_description = "Batch Details"

    def billing_document_link(self, obj):
        if obj.billing_document:
            url = reverse(
                'admin:costing_billingdocumentheader_change',
                args=[obj.billing_document.pk]
            )
            return format_html('<a href="{}">{}</a>', url, obj.billing_document.base_number)
        return "-"
    
    billing_document_link.short_description = "Billing Document"

    def load_total_display(self, obj):
        total = obj.load_total_quantity
        if total is None:
            return "-"
        return f"{total:.0f}"

    load_total_display.short_description = "Load Total Qty"
    
    # ============= DOCUMENT DISPLAY METHODS =============
    
    def delivery_note_display(self, obj):
        return self._render_document_section(obj, 'delivery_note', 'Delivery Note')
    delivery_note_display.short_description = "Delivery Note"
    
    def namra_display(self, obj):
        return self._render_document_section(obj, 'namra', 'NAMRA')
    namra_display.short_description = "NAMRA"
    
    def daff_display(self, obj):
        return self._render_document_section(obj, 'daff', 'DAFF')
    daff_display.short_description = "DAFF"
    
    def meat_board_display(self, obj):
        return self._render_document_section(obj, 'meat_board', 'Meat Board')
    meat_board_display.short_description = "Meat Board"
    
    def import_permit_display(self, obj):
        return self._render_document_section(obj, 'import_permit', 'Import Permit')
    import_permit_display.short_description = "Import Permit"
    
    def _render_document_section(self, obj, doc_type, label):
        """Render ONLY the Add button - clean minimal version"""
        if not obj.pk:
            return ""
        
        docs = getattr(obj, f'{doc_type}_documents', [])
        
        html = '<div style="margin: 5px 0;">'
        
        # Hidden list for uploaded documents
        html += f'<ul class="{doc_type}-doc-list" style="list-style: none; padding: 0; margin: 0 0 5px 0;">'
        
        for doc in docs:
            html += f'''
            <li class="{doc_type}-doc-item" style="margin-bottom: 5px;">
                <a href="/media/{escape(doc['file'])}" target="_blank" style="color: #417690; font-size: 12px;">{escape(doc['filename'])}</a>
                <button type="button"
                        class="{doc_type}-remove-row"
                        data-doc-id="{doc['id']}"
                        style="margin-left:5px; border:none; background:none; color:#d32f2f; font-weight:bold; cursor:pointer; font-size: 16px;">×</button>
            </li>
            '''
        
        html += '</ul>'
        
        # Hidden file input container
        html += f'<div class="{doc_type}-file-rows" style="display:none;"></div>'
        
        # ONLY the Add button
        html += f'''
        <button type="button" 
                class="{doc_type}-add-row" 
                style="background: #417690; color: white; border: none; padding: 6px 12px; cursor: pointer; border-radius: 3px; font-size: 12px;">
            + Add
        </button>
        '''
        
        html += '</div>'
        
        return mark_safe(html)

    
    ordering = ['-released_date', '-load_number']
    list_per_page = 50
    
    def get_readonly_fields(self, request, obj=None):
        base_readonly = list(self.readonly_fields)
        
        if obj is None:
            base_readonly.extend(['billing_document'])
        
        return base_readonly
    
    def has_add_permission(self, request):
        # Transport Loads are created automatically by PickingSlip signal
        return False
    
    def has_delete_permission(self, request, obj=None):
        if obj and obj.released_date:
            return False
        return True
    
    def save_model(self, request, obj, form, change):
        """Handle file uploads for all document types"""
        super().save_model(request, obj, form, change)
        
        doc_types = ['delivery_note', 'namra', 'daff', 'meat_board', 'import_permit']
        
        documents_changed = False
        
        # Handle standard document types (existing code)
        for doc_type in doc_types:
            files = request.FILES.getlist(f'{doc_type}_file[]')
            delete_ids = request.POST.getlist(f'delete_{doc_type}_ids[]')
            
            current_docs = getattr(obj, f'{doc_type}_documents', [])
            if not isinstance(current_docs, list):
                current_docs = []
            
            if delete_ids:
                current_docs = [d for d in current_docs if str(d.get('id')) not in delete_ids]
                documents_changed = True
            
            if files:
                from django.core.files.storage import default_storage
                import uuid
                
                for file in files:
                    file_path = default_storage.save(f'transport_docs/{obj.load_number}_{file.name}', file)
                    current_docs.append({
                        'id': str(uuid.uuid4()),
                        'file': file_path,
                        'filename': file.name,
                    })
                    documents_changed = True
            
            setattr(obj, f'{doc_type}_documents', current_docs)
        
        # ✅ Handle other/custom documents
        other_docs = obj.other_documents if obj.other_documents else []
        if not isinstance(other_docs, list):
            other_docs = []

        # Add new categories with their files
        new_category_names = request.POST.getlist('new_other_doc_name[]')

        for cat_idx, cat_name in enumerate(new_category_names):
            if not cat_name.strip():
                continue
            
            # Create new category
            new_category = {
                'name': cat_name.strip(),
                'files': []
            }
            
            # Get files for this new category (indexed by new_0, new_1, etc.)
            new_idx = f'new_{cat_idx}'
            files = request.FILES.getlist(f'other_file_{new_idx}[]')
            
            if files:
                from django.core.files.storage import default_storage
                import uuid
                
                for file in files:
                    file_path = default_storage.save(f'transport_docs/{obj.load_number}_{file.name}', file)
                    new_category['files'].append({
                        'id': str(uuid.uuid4()),
                        'file': file_path,
                        'filename': file.name,
                    })
                    documents_changed = True
            
            other_docs.append(new_category)
            documents_changed = True

        # Handle existing categories - add/remove files
        for idx, category in enumerate(other_docs):
            files = request.FILES.getlist(f'other_file_{idx}[]')
            delete_file_ids = request.POST.getlist(f'delete_other_file_{idx}[]')
            
            if delete_file_ids:
                category['files'] = [
                    f for f in category['files']
                    if str(f.get('id')) not in delete_file_ids
                ]
                documents_changed = True
            
            if files:
                from django.core.files.storage import default_storage
                import uuid
                
                for file in files:
                    file_path = default_storage.save(f'transport_docs/{obj.load_number}_{file.name}', file)
                    category['files'].append({
                        'id': str(uuid.uuid4()),
                        'file': file_path,
                        'filename': file.name,
                    })
                    documents_changed = True

        # Remove categories marked for deletion
        remove_categories = request.POST.getlist('remove_other_category[]')
        if remove_categories:
            other_docs = [
                cat for i, cat in enumerate(other_docs)
                if str(i) not in remove_categories
            ]
            documents_changed = True

        obj.other_documents = other_docs

        # Save if there were changes
        if documents_changed:
            obj.save(update_fields=[
                'delivery_note_documents',
                'namra_documents', 
                'daff_documents',
                'meat_board_documents',
                'import_permit_documents',
                'other_documents',
            ])



@admin.register(DeliverySite)
class DeliverySiteAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    list_display = (
        "client",
        "institutionname",
        "city",
        "province",
        "country",
        "contact_person",
        "phone",
        "email",
    )

    search_fields = (
        "institutionname",
        "client__name",
        "client__legal_name",
        "city",
        "province",
        "contact_person",
        "phone",
        "email",
    )

    list_filter = ("country", "province", "city")

    fieldsets = (
        ("Client", {
            "fields": ("client",)
        }),
        ("Site details", {
            "fields": (
                "institutionname",
                "address_line1",
                "address_line2",
                "city",
                "province",
                "postal_code",
                "country",
            )
        }),
        ("Contact", {
            "fields": (
                "contact_person",
                "phone",
                "email",
            )
        }),
    )
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Filter client choices based on site context:
        - HQ: show only HQ clients (site=NULL)
        - Site: show only clients for that specific site
        """
        if db_field.name == 'client':
            site_id = request.session.get('current_site_id')
            
            if site_id:
                # Site context: show only clients for this site
                kwargs['queryset'] = Client.objects.filter(site_id=site_id, is_archived=False)
            else:
                # HQ context: show only HQ clients (site=NULL)
                kwargs['queryset'] = Client.objects.filter(site__isnull=True, is_archived=False)
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
