# -*- coding: utf-8 -*-

from openerp import models, fields, api, exceptions

REJECT_TYPES = [('warning', 'Attention'), ('info', 'Information'), ('error', 'Erreur')]

class reject(models.TransientModel):

    _name = 'reject'

    type_msg = fields.Selection(REJECT_TYPES, string='Type', readonly=True)
    title = fields.Char(string=u"Titre", size=100, readonly=True)
    message_w = fields.Text(string=u"Méssage", readonly=True)
    motif_reject = fields.Text(string=u"Motif du rejet", required=True, default="")
    ask_mission_id = fields.Integer(string=u"Demande de mission")

    def _get_view_id(self):
        """Get the view id
        @return: view id, or False if no view found
        """
        res = self.env['ir.model.data'].get_object_reference('voyage_module', 'warning_form')
        return res and res[1] or False

    @api.multi
    def message(self, ids):
        message = self.browse(ids)
        message_type = [t[1] for t in REJECT_TYPES if message.type_msg == t[0]][0]
        print '%s: %s' % (message_type, message.title)
        res = {
            'name': '%s: %s' % (message_type, message.title),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': self._get_view_id(),
            'res_model': 'warning',
            'domain': [],
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': message.id
        }
        return res

    @api.multi
    def warning(self, title, message):
        record = self.create({'title': title, 'message_w': message, 'type_msg': 'warning'})
        res = self.message(record.id)
        return res

    @api.multi
    def info(self, title, message, ask_mission_id):
        record = self.create({'title': title, 'message_w': message, 'type_msg': 'info', 'ask_mission_id': ask_mission_id})
        res = self.message(record.id)
        return res

    @api.multi
    def error(self, title, message):
        record = self.create({'title': title, 'message_w': message, 'type_msg': 'error'})
        res = self.message(record.id)
        return res

    @api.multi
    def action_confirm_reject(self):
        for rec in self:
            return self.env['demande.mission'].search([('id', '=', rec.ask_mission_id)]).write({'motif_reject': rec.motif_reject, 'state': 'reject'})