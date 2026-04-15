# -*- coding: utf-8 -*-
{
    'name': 'BuildingPay v25',
    'version': '17.0.1.0.0',
    'category': 'Custom',
    'summary': 'BuildingPay v25 - Gestione Amministratori Condomini e Pagamenti PagoPa',
    'description': """
BuildingPay - Modulo per la gestione degli amministratori di condomini,
portale web per registrazione e gestione contratti, importazione fatture
PagoPa e retrocessioni verso amministratori e referrer.
    """,
    'author': 'Progetto e Soluzioni',
    'website': 'https://www.progettiesoluzioni.it',
    'license': 'OPL-1',
    'depends': [
        'base',
        'base_setup',
        'website',
        'portal',
        'account',
        'purchase',
        'product',
        'mail',
        'auth_signup',
        'l10n_it_edi',
    ],
    'data': [
        # Security (load first)
        'security/buildingpay_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        # Views
        'views/buildingpay_config_views.xml',
        'views/res_partner_views.xml',
        'views/product_pricelist_views.xml',
        'views/product_template_views.xml',
        'views/buildingpay_import_views.xml',
        'views/buildingpay_menus.xml',
        # Portal templates
        'templates/portal_home_inherit.xml',
        'templates/portal_registration.xml',
        'templates/portal_contratto.xml',
        'templates/portal_condomini.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
