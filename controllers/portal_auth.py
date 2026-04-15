# -*- coding: utf-8 -*-
import uuid
import logging
from odoo import http, fields as odoo_fields, _
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome

_logger = logging.getLogger(__name__)


class BuildingPaySignup(AuthSignupHome):
    """
    Estende il controller di registrazione standard di Odoo per:
    1. Mostrare campi aggiuntivi (nome, indirizzo, CF/P.IVA, IBAN, banca)
    2. Catturare il codice referrer dall'URL
    3. Dopo la registrazione, configurare il partner come Amministratore
       e collegare il referrer
    4. Creare il record res.partner.bank con l'IBAN inserito
    5. Inviare l'email di benvenuto
    """

    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        """
        Override del form di registrazione.
        Il link BuildingPay ha la forma: /web/signup?referrer=CODICE123
        """
        # ------------------------------------------------------------------
        # BYPASS 1: inviti via token (es. "Concedi accesso portale" dal backend)
        # ------------------------------------------------------------------
        token = kw.get('token') or request.params.get('token', '')
        if token:
            return super().web_auth_signup(*args, **kw)

        # Salva il referrer_code in sessione se presente nell'URL (GET) o nel form (POST).
        referrer_code = (
            kw.get('referrer')
            or request.params.get('referrer', '')
            or kw.get('referrer_code')
            or request.params.get('referrer_code', '')
        )
        if referrer_code:
            request.session['buildingpay_referrer_code'] = referrer_code

        # ------------------------------------------------------------------
        # BYPASS 2: nessuna configurazione BuildingPay per questo sito web
        # ------------------------------------------------------------------
        config = request.env['buildingpay_v25.config'].sudo().get_config_for_website()
        if not config:
            return super().web_auth_signup(*args, **kw)

        # Prepara qcontext con i dati custom
        qcontext = self.get_auth_signup_qcontext()
        qcontext['referrer_code'] = referrer_code or request.session.get(
            'buildingpay_referrer_code', '')

        # Elenco banche per il select nel form (popolato da res.bank)
        qcontext['banks'] = request.env['res.bank'].sudo().search([], order='name')

        # Se il referrer_code è valido, mostriamo il nome del referrer
        if qcontext.get('referrer_code'):
            referrer = request.env['res.partner'].sudo().search([
                ('referrer_code', '=', qcontext['referrer_code']),
                ('is_amministratore', '=', True),
            ], limit=1)
            qcontext['referrer_partner'] = referrer

        if request.httprequest.method == 'GET':
            return request.render('BuildingPay_v25.signup_form', qcontext)

        # POST: elabora il form BuildingPay
        return self._process_buildingpay_signup(qcontext, **kw)

    def _process_buildingpay_signup(self, qcontext, **kw):
        """
        Elabora il form di registrazione BuildingPay.

        Strategia (v25 — fix definitivo dei regression bug):
        ─────────────────────────────────────────────────────
        Il problema principale delle versioni precedenti era che i campi
        is_amministratore e privacy_accepted hanno tracking=True nel modello.
        Quando il write() invocava il meccanismo di tracking di Odoo per creare
        un mail.message, la creazione falliva per il nuovo utente portale (che non
        ha ancora un mail thread inizializzato) causando il rollback via savepoint
        dell'INTERO write(). Poichè l'eccezione non veniva propagata al nostro
        try/except (Odoo la cattura internamente nel savepoint), la transazione
        rimaneva in stato ABORTED e tutti i write successivi fallivano in silenzio.

        Soluzione adottata in v25:
        1. Recupera TUTTI i valori del form PRIMA del signup.
        2. Crea l'utente via res.users.signup() (metodo MODEL — senza commit né
           authenticate).
        3. Trova partner_id via SQL diretto (bypassando la cache ORM).
        4. Esegue UN UNICO write() combinato su tutti i campi del partner, con
           context tracking_disable=True + mail_notrack=True per disabilitare
           il mail tracking. Viene incluso anche referrer_code generato qui
           (così il write() override del modello non fa un secondo write per
           generarlo, evitando la catena di write annidati).
        5. Partita IVA in write separato (ha validazione ORM propria).
        6. Crea res.partner.bank se IBAN fornito.
        7. Commit unico di tutto.
        8. Autentica la sessione DOPO il commit.
        9. Redirect a /my (home portale).
        """
        params = request.params

        # ------------------------------------------------------------------
        # Validazione campi obbligatori
        # ------------------------------------------------------------------
        errors = {}

        required_fields = ['name', 'login', 'password', 'confirm_password',
                           'street', 'city', 'zip']
        for field in required_fields:
            if not params.get(field, '').strip():
                errors[field] = _('Campo obbligatorio')

        if params.get('password') != params.get('confirm_password'):
            errors['confirm_password'] = _('Le password non coincidono')

        iban = params.get('iban', '').strip().replace(' ', '')
        if iban and len(iban) < 15:
            errors['iban'] = _('IBAN non valido (lunghezza minima 15 caratteri)')

        if not params.get('privacy_accepted'):
            errors['privacy_accepted'] = _('Devi accettare la Privacy Policy per registrarti')

        if errors:
            qcontext.update({'error': errors, 'form_data': params})
            if 'banks' not in qcontext:
                qcontext['banks'] = request.env['res.bank'].sudo().search([], order='name')
            return request.render('BuildingPay_v25.signup_form', qcontext)

        login = params.get('login', '').strip()
        password = params.get('password', '')
        name = params.get('name', '').strip()

        # ------------------------------------------------------------------
        # Cattura TUTTI i valori dai params PRIMA del signup.
        # Dopo session.authenticate() la sessione viene rigenerata e i valori
        # (es. buildingpay_referrer_code) vengono persi.
        # ------------------------------------------------------------------
        referrer_code_local = (
            params.get('referrer_code', '').strip()
            or qcontext.get('referrer_code', '')
            or request.session.get('buildingpay_referrer_code', '')
        )
        privacy_accepted = bool(params.get('privacy_accepted'))

        # Banca: priorità al testo libero (banca_nome), poi al select (banca_select)
        banca_nome_raw = params.get('banca_nome', '').strip()
        banca_select = params.get('banca_select', '').strip()
        if banca_nome_raw:
            banca_nome_local = banca_nome_raw
        elif banca_select and banca_select != '__altra__':
            banca_nome_local = banca_select
        else:
            banca_nome_local = ''

        vat_local = params.get('vat', '').strip()
        raw_country = params.get('country_id', '') or ''
        state_code = params.get('state_code', '').strip().upper()

        # ------------------------------------------------------------------
        # Step 1: Crea l'utente via res.users.signup() (metodo MODEL).
        # In Odoo 17 restituisce (db, login) — 2 valori.
        # ------------------------------------------------------------------
        try:
            signup_result = request.env['res.users'].sudo().signup(
                {'login': login, 'name': name, 'password': password}
            )
            db = signup_result[0]
            login_result = signup_result[1]
        except Exception as e:
            _logger.error('BuildingPay signup – errore creazione utente: %s', e)
            qcontext['error'] = {
                'general': _('Errore durante la creazione dell\'account: %s') % str(e)
            }
            if 'banks' not in qcontext:
                qcontext['banks'] = request.env['res.bank'].sudo().search([], order='name')
            return request.render('BuildingPay_v25.signup_form', qcontext)

        # ------------------------------------------------------------------
        # Step 2: Recupera partner_id via SQL diretto.
        # SQL diretto bypasssa la cache ORM (che potrebbe non essere aggiornata
        # dopo signup) e legge il dato direttamente dalla transazione corrente.
        # ------------------------------------------------------------------
        partner_id = None
        try:
            cr = request.env.cr
            cr.execute(
                'SELECT partner_id FROM res_users WHERE login = %s LIMIT 1',
                (login_result,)
            )
            row = cr.fetchone()
            if row:
                partner_id = row[0]
        except Exception as e:
            _logger.error('BuildingPay signup – errore SQL lettura partner_id: %s', e)

        if not partner_id:
            _logger.error(
                'BuildingPay signup – partner_id non trovato per login=%s', login_result)
            try:
                request.env.cr.commit()
                request.session.authenticate(db, login_result, password)
            except Exception:
                pass
            return request.redirect('/my')

        # Context che disabilita COMPLETAMENTE il mail tracking di Odoo.
        # Senza questo, i campi con tracking=True (is_amministratore, privacy_accepted)
        # tentano di creare mail.message che fallisce per il nuovo utente portale,
        # causando rollback silenzioso dell'intero write() via savepoint Odoo.
        NO_TRACK_CTX = {'tracking_disable': True, 'mail_notrack': True}

        partner = request.env['res.partner'].sudo().with_context(**NO_TRACK_CTX).browse(
            partner_id)

        if not partner.exists():
            _logger.error(
                'BuildingPay signup – browse partner_id=%s ha restituito recordset vuoto',
                partner_id)
            try:
                request.env.cr.commit()
                request.session.authenticate(db, login_result, password)
            except Exception:
                pass
            return request.redirect('/my')

        # ------------------------------------------------------------------
        # Step 3: Costruisce il dict con TUTTI i campi da scrivere sul partner.
        # Includiamo il referrer_code generato qui: così il write() override
        # del modello vede già referrer_code valorizzato e NON fa un secondo
        # write() per generarlo (evitando write() annidati che potrebbero fallire).
        # ------------------------------------------------------------------
        write_vals = {
            'is_amministratore': True,
            'lang': 'it_IT',
            'referrer_code': uuid.uuid4().hex[:8].upper(),
        }

        if privacy_accepted:
            write_vals['privacy_accepted'] = True
            write_vals['privacy_accepted_date'] = odoo_fields.Datetime.now()

        # Dati anagrafici
        for field in ['street', 'street2', 'city', 'zip', 'phone']:
            val = params.get(field, '').strip()
            if val:
                write_vals[field] = val

        if params.get('fiscalcode', '').strip():
            write_vals['fiscalcode'] = params['fiscalcode'].strip()

        # Referrer
        if referrer_code_local:
            try:
                _logger.info('BuildingPay signup: cerco referrer con codice "%s"',
                             referrer_code_local)
                referrer = request.env['res.partner'].sudo().search([
                    ('referrer_code', '=', referrer_code_local),
                ], limit=1)
                if referrer:
                    write_vals['referrer_id'] = referrer.id
                    _logger.info('BuildingPay signup: referrer_id=%s (%s)',
                                 referrer.id, referrer.name)
                else:
                    _logger.warning(
                        'BuildingPay signup: nessun partner con referrer_code="%s"',
                        referrer_code_local)
            except Exception as e:
                _logger.warning('BuildingPay signup – errore ricerca referrer: %s', e)

        # Paese e provincia
        try:
            if raw_country:
                cid = int(raw_country)
                if cid:
                    write_vals['country_id'] = cid

            if state_code:
                state_domain = [('code', '=', state_code)]
                if write_vals.get('country_id'):
                    state_domain.append(('country_id', '=', write_vals['country_id']))
                state = request.env['res.country.state'].sudo().search(
                    state_domain, limit=1)
                if state:
                    write_vals['state_id'] = state.id
        except (ValueError, TypeError) as e:
            _logger.warning('BuildingPay signup – country/state non valido: %s', e)

        # ------------------------------------------------------------------
        # Step 4: UNICO write() con tracking_disable=True su TUTTI i campi.
        # ------------------------------------------------------------------
        try:
            partner.write(write_vals)
            _logger.info('BuildingPay signup: write() principale OK – partner %s',
                         partner_id)
        except Exception as e:
            _logger.error('BuildingPay signup – errore write() principale: %s', e)

        # ------------------------------------------------------------------
        # Step 5: Partita IVA — write separato (ha validazione ORM).
        # ------------------------------------------------------------------
        if vat_local:
            try:
                partner.write({'vat': vat_local})
            except Exception as e:
                _logger.warning('BuildingPay signup – P.IVA non valida (%s): %s',
                                vat_local, e)

        # ------------------------------------------------------------------
        # Step 6: IBAN → crea res.partner.bank.
        # ------------------------------------------------------------------
        if iban:
            try:
                bank_vals = {
                    'partner_id': partner_id,
                    'acc_number': iban,
                }

                if banca_nome_local:
                    res_bank = request.env['res.bank'].sudo().search(
                        [('name', '=ilike', banca_nome_local)], limit=1)
                    if not res_bank:
                        res_bank = request.env['res.bank'].sudo().create(
                            {'name': banca_nome_local})
                        _logger.info('BuildingPay signup: creata nuova banca "%s" (id=%s)',
                                     banca_nome_local, res_bank.id)
                    else:
                        _logger.info('BuildingPay signup: banca trovata "%s" (id=%s)',
                                     res_bank.name, res_bank.id)
                    bank_vals['bank_id'] = res_bank.id

                request.env['res.partner.bank'].sudo().with_context(**NO_TRACK_CTX).create(
                    bank_vals)
                _logger.info('BuildingPay signup: IBAN salvato – partner %s', partner_id)
            except Exception as e:
                _logger.warning('BuildingPay signup – errore creazione IBAN: %s', e)

        # ------------------------------------------------------------------
        # Step 7: Commit unico — salva tutto in un'unica operazione atomica.
        # ------------------------------------------------------------------
        try:
            request.env.cr.commit()
            _logger.info('BuildingPay signup: commit OK – partner %s', partner_id)
        except Exception as e:
            _logger.error('BuildingPay signup – errore commit: %s', e)
            return request.redirect('/my')

        # ------------------------------------------------------------------
        # Step 8: Autentica la sessione DOPO il commit.
        # ------------------------------------------------------------------
        try:
            request.session.authenticate(db, login_result, password)
        except Exception as e:
            _logger.warning('BuildingPay signup – errore autenticazione sessione: %s', e)

        # Pulisci il referrer dalla sessione
        request.session.pop('buildingpay_referrer_code', None)

        # Email di benvenuto (inviata dopo commit + authenticate)
        try:
            partner_fresh = request.env['res.partner'].sudo().browse(partner_id)
            if partner_fresh.exists():
                self._send_welcome_email(partner_fresh)
        except Exception as e:
            _logger.warning('BuildingPay signup – errore email benvenuto: %s', e)

        _logger.info('BuildingPay: nuovo amministratore registrato: login=%s partner_id=%s',
                     login_result, partner_id)

        return request.redirect('/my')

    def _send_welcome_email(self, partner):
        """Invia l'email di benvenuto al nuovo amministratore."""
        try:
            template = request.env.ref(
                'BuildingPay_v25.email_template_benvenuto_amministratore',
                raise_if_not_found=False,
            )
            if template:
                template.sudo().send_mail(partner.id, force_send=True)
        except Exception as e:
            _logger.error('BuildingPay: errore invio email benvenuto: %s', e)

    def _get_referral_url(self, partner):
        """Genera il link referral per un amministratore."""
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        if partner.referrer_code:
            return '%s/web/signup?referrer=%s' % (base_url, partner.referrer_code)
        return base_url
