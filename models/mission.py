# -*- coding:utf-8 -*-

from openerp import models, fields, api, exceptions
from datetime import date, datetime, timedelta
import time
import openerp.addons.decimal_precision as dp
from openerp.exceptions import Warning as UserError

STATES = [('draft', u'Brouillon'), ('cancel', u"Rejetée"), ('confirm', u"En attente d'approbation"), ('first_validate', u'Responsable / Chef de services'), ('second_validate', u'Directeur Général'), ('cancelled', u'Demande rejetée'), ('done', u'Validée')]

class voyage_demande_mission(models.Model):

    _name = "demande.mission"
    _inherit = ['mail.thread', 'ir.needaction_mixin']


# ----------------------------------------------- Default dependences --------------------------------------------------

    @api.model
    def _get_current_user(self):
        return self.env['res.users'].browse(self.env.uid)

    @api.model
    def _get_job_position(self, cr, uid, ids, context=None):
        res = []
        for employee in self.pool.get('hr.employee').browse(cr, uid, ids, context=context):
            if employee.job_id:
                res.append(employee.job_id.id)
        return res

    @api.model
    def _get_current_dep(self):
        current_user = self.env['res.users'].browse(self.env.uid)
        current_emp = self.env['hr.employee'].search([('user_id', '=', current_user.id)])
        return self.env['hr.department'].search([('id', '=', current_emp.department_id.id)])

    @api.model
    def _get_current_job(self):
        current_user = self.env['res.users'].browse(self.env.uid)
        current_emp = self.env['hr.employee'].search([('user_id', '=', current_user.id)])
        return self.env['hr.job'].search([('id', '=', current_emp.job_id.id)])

    @api.model
    def _get_current_parent(self):
        current_user = self.env['res.users'].browse(self.env.uid)
        current_emp = self.env['hr.employee'].search([('user_id', '=', current_user.id)])
        return self.env['hr.employee'].search([('id', '=', current_emp.parent_id.id)])

    @api.model
    def _get_current_category(self):
        current_user = self.env['res.users'].browse(self.env.uid)
        current_emp = self.env['hr.employee'].search([('user_id', '=', current_user.id)])
        return self.env['hr.employee.category'].search([('id', '=', current_emp.category_ids.id)])

    @api.model
    def _get_current_company_country(self):
        current_user = self.env['res.users'].browse(self.env.uid)
        current_emp = self.env['hr.employee'].search([('user_id', '=', current_user.id)])
        return self.env['res.country'].search([('id', '=', current_emp.country_id.id)])

    def expense_canceled(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'cancelled'}, context=context)

# ----------------------------------------------- Calcul de la date ----------------------------------------------------

    # @api.multi
    # def compare_date(self):
    #     if self.from_date < self.final_date:
    #         raise UserError(u"La date de départ doit toujours être supérieure a la date initiale de la demande")

    @api.multi
    def _get_datetime_ask(self):
        date_now = datetime.strftime(datetime.today(), "%Y-%m-%d %H:%M:%S")
        return date_now

    @api.onchange('from_date', 'final_date', 'total_days')
    def calculate_date(self):
        if self.from_date and self.final_date:
            d1 = datetime.strptime(str(self.from_date), '%Y-%m-%d')
            d2 = datetime.strptime(str(self.final_date), '%Y-%m-%d')
            d3 = d2 - d1
            self.total_days = str(d3.days)

    @api.onchange('record_date', 'from_date', 'diff_days')
    def validate_date(self):
        if self.record_date and self.from_date:
            d4 = datetime.strptime(str(self.record_date), '%Y-%m-%d')
            d5 = datetime.strptime(str(self.from_date), '%Y-%m-%d')
            d6 = d5 - d4
            self.diff_days = str(d6.days)


# ----------------------------------------- Changement de ville en pays ------------------------------------------------

    @api.multi
    def onchange_state(self, state_id):
        if state_id:
            state = self.env['res.country.state'].browse(state_id)
            return {'value': {'country_id': state.country_id.id}}
        return {}

    @api.multi
    def onchange_state_destination(self, state_id_destination):
        if state_id_destination:
            state_destination = self.env['res.country.state'].browse(state_id_destination)
            return {'value': {'country_id_destination': state_destination.country_id.id}}
        return {}

# ----------------------------------------- Action des bouttons du workflow --------------------------------------------

    @api.multi
    @api.depends('record_date', 'name',
                 'company_id', 'user', 'manager_dept',
                 'department_id', 'etiquette', 'grade', 'objet', 'state_id', 'country_id',
                 'state_id_destination', 'country_id_destination', 'from_date', 'final_date',
                 'total_days', 'diff_days', 't_transport', 'documents')
    def _compute_is_editable(self):
        for rec in self:
            if rec.state in ('confirm', 'cancel', 'first_validate', 'second_validate', 'cancelled', 'done'):
                rec.is_editable = False
            else:
                rec.is_editable = True

# ----------------------------------------- Notifications --------------------------------------------------------------

    _track = {
        'state': {
            'request_module.mt_request_to_confirm_first':
                lambda self, cr, uid, obj,
                       ctx=None: obj.state == 'confirm',
            'request_module.mt_request_to_approve_subscription':
                lambda self, cr, uid, obj,
                       ctx=None: obj.state == 'validate_draft',
            'request_module.mt_request_to_reject_subscription':
                lambda self, cr, uid, obj,
                       ctx=None: obj.state == 'reject_draft',
            'request_module.mt_request_to_put_in_draft':
                lambda self, cr, uid, obj,
                       ctx=None: obj.state == 'put_in_draft',
            'voyage_module.mt_request_to_confirm_serv_support':
                lambda self, cr, uid, obj,
                       ctx=None: obj.state == 'first_validate',
            'voyage_module.mt_request_to_confirm_two':
                lambda self, cr, uid, obj,
                       ctx=None: obj.state == 'second_validate',
            'voyage_module.mt_request_done':
                lambda self, cr, uid, obj,
                       ctx=None: obj.state == 'done',
            'voyage_module.mt_request_reject':
                lambda self, cr, uid, obj,
                       ctx=None: obj.state == 'cancelled',
        },
    }

    # @api.model
    # def create(self, vals):
    #     if vals.get('manager_dept'):
    #         manager_dept = self.env['hr.employee'].browse(vals.get('manager_dept'))
    #         vals['message_follower_ids'] = [(4, manager_dept.user_id.id)]
    #     return super(voyage_demande_mission, self).create(vals)

    # @api.multi
    # def write(self, vals):
    #     self.ensure_one()
    #     vals['record_date'] = time.strftime('%Y-%m-%d')
    #     if vals.get('manager_dept'):
    #         manager_dept = self.env['hr.employee'].browse(vals.get('manager_dept'))
    #         vals['message_follower_ids'] = [(4, manager_dept.user_id.id)]
    #     res = super(voyage_demande_mission, self).write(vals)
    #     return res

# ----------------------------------------- Action des bouttons du workflow --------------------------------------------
    @api.multi
    def action_button_confirm(self):
        for o in self:
            if o.total_days <= 0:
                raise UserError(u"La date de départ doit toujours être supérieure a la date de d'arrivé")
            if o.diff_days <= 7:
                raise UserError(u"La marge de demande de mission se doit d'être de sept (7) jours minimum")
            if o.diff_days <= 0:
                raise UserError(u"La date de départ doit toujours être supérieure a la date initiale de la demande")
        self.state = 'confirm'
        return True

    @api.multi
    def validate_draft(self):
        self.state = 'first_validate'
        return True

    @api.multi
    def reject_draft(self):
        self.state = 'cancel'
        return True

    @api.multi
    def put_in_draft(self):
        self.state = 'draft'
        return True

    @api.multi
    def first_validate_ask(self):
        self.state = 'second_validate'
        return True

    @api.multi
    def first_reject_ask(self):
        self.state = 'cancelled'
        return self.env['info'].info(title='Motif du rejet', message="Donner le motif du rejet", demande_id=self.ids[0])

    @api.multi
    def second_validate_ask(self):
        self.state = 'done'
        return True

    @api.multi
    def second_reject_ask(self):
        self.state = 'cancelled'
        return self.env['info'].info(title='Motif du rejet', message="Donner le motif du rejet", demande_id=self.ids[0])

    record_date = fields.Date(string=u"Date", default=_get_datetime_ask, readonly=False, track_visibility='onchange')

    diff_days = fields.Integer(string=u"Durée", readonly=False, track_visibility='onchange')

    name = fields.Many2one(comodel_name='hr.employee', string=u"Nom de l'employé", default=lambda self: self.env.user.id, store=True, readonly=False, track_visibility='onchange')

    company_id = fields.Many2one(comodel_name='res.company', string=u"Société", default=lambda self: self.env.user.company_id.id, store=True, readonly=False, track_visibility='onchange')

    user = fields.Many2one(comodel_name='res.users', string=u"Nom de l'utilisateur", track_visibility='onchange', default=_get_current_user, store=True, readonly=False)

    # user_id = fields.Many2one(comodel_name='res.users', track_visibility='onchange')

    manager_dept = fields.Many2one(comodel_name='hr.employee', string=u"Responsable", default=_get_current_parent, store=True, readonly=False, track_visibility='onchange')

    department_id = fields.Many2one(comodel_name='hr.department', string=u"Département", default=_get_current_dep, store=True, readonly=False, track_visibility='onchange')

    etiquette = fields.Many2one(comodel_name='hr.employee.category', string=u"Etiquette", default=_get_current_category, store=True, readonly=False)

    grade = fields.Many2one(comodel_name='hr.job', string=u"Poste", required=True, default=_get_current_job, store=True, readonly=False)

    objet = fields.Many2one(comodel_name='type.mission', string=u"Objet de la mission", required=True, readonly=False)

    state_id = fields.Many2one(comodel_name='res.country.state', string=u'Ville de départ', required="true", readonly=False)

    country_id = fields.Many2one(comodel_name='res.country', string=u"Pays de départ", default=_get_current_company_country, store=True, required=True, readonly=False)

    state_id_destination = fields.Many2one(comodel_name='res.country.state', string=u"Ville de destination", required=True, readonly=False)

    country_id_destination = fields.Many2one(comodel_name='res.country', string=u"Pays de destination", required=True, store=True, readonly=False)

    from_date = fields.Date(string=u"Du : ", required=True, readonly=False)

    final_date = fields.Date(string=u"Au : ", required=True, readonly=False)

    total_days = fields.Integer(string=u"Durée (/Jours) :", store=True, readonly=False)

    # t_transport = fields.Selection(((('1','Avion'), ('2','Bateau'), ('3','Voiture'))), default='1', string="Type de transport", required=True, readonly=False)

    t_transport = fields.Many2one(comodel_name='type.transport', string=u"Type de transport", required=True, readonly=False)

    documents = fields.Many2many(comodel_name='ir.attachment', string=u"Joindre un document", required=True, readonly=False, track_visibility='onchange')

    is_editable = fields.Boolean(string="Is editable", compute="_compute_is_editable", readonly=True)

    motif_reject = fields.Text(string=u"Motif de rejet", track_visibility='onchange')

    state = fields.Selection(STATES ,string=u'Statut demande de mission', required=True, readonly=True, default='draft', track_visibility='onchange')


# ---------------------------------------------- Type de mission -------------------------------------------------------


class type_mission(models.Model):

    _name = "type.mission"

    @api.model
    def _get_current_dep(self):
        current_user = self.env['res.users'].browse(self.env.uid)
        current_emp = self.env['hr.employee'].search([('user_id', '=', current_user.id)])
        return self.env['hr.department'].search([('id', '=', current_emp.department_id.id)])

    name = fields.Char(string=u'Type de mission', required=True)

    departement_id = fields.Many2one(comodel_name='hr.department', string=u'Département', required=True, store=True, default=_get_current_dep)

    description = fields.Text(string=u"Description", required=True)


# ---------------------------------------------- Type de transport -----------------------------------------------------

class type_transport(models.Model):

    _name = "type.transport"

    name = fields.Char(string=u'Type de transport', required=True)

