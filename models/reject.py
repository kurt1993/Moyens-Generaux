# -*- coding: utf-8 -*-

from openerp import models, fields, api, exceptions

TYPE_MESSAGE = [('warning', 'Attention'), ('info', 'Information'), ('error', 'Erreur')]

class info(models.TransientModel):

    _name = 'info'
    _description = 'info'

    type_message = fields.Selection(TYPE_MESSAGE, string='Type', readonly=True)
    title = fields.Char(string=u"Titre", size=100, readonly=True)
    message_e = fields.Text(string=u"Message", readonly=True)
    motif_message = fields.Text(string=u"Motif du rejet", required=True, default="")
    demande_id = fields.Integer(string=u"Demande de mission")

    def _get_view_id(self):
        """Get the view id
        @return: view id, or False if no view found
        """
        res = self.env['ir.model.data'].get_object_reference('voyage_module', 'info_form')
        return res and res[1] or False

    @api.multi
    def message(self, ids):
        message = self.browse(ids)
        message_type = [t[1] for t in TYPE_MESSAGE if message.type_message == t[0]][0]
        print '%s: %s' % (message_type, message.title)
        res = {
            'name': '%s: %s' % (message_type, message.title),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': self._get_view_id(),
            'res_model': 'info',
            'domain': [],
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': message.id
        }
        return res

    @api.multi
    def warning(self, title, message):
        record = self.create({'title': title, 'message_e': message, 'type_message': 'warning'})
        res = self.message(record.id)
        return res

    @api.multi
    def info(self, title, message, demande_id):
        record = self.create({'title': title, 'message_e': message, 'type_message': 'info', 'demande_id': demande_id})
        res = self.message(record.id)
        return res

    @api.multi
    def error(self, title, message):
        record = self.create({'title': title, 'message_e': message, 'type_message': 'error'})
        res = self.message(record.id)
        return res

    @api.multi
    def action_confirm_reject(self):
        for rec in self:
            return self.env['demande.mission'].search([('id', '=', rec.demande_id)]).write({'motif_message': rec.motif_message, 'state': 'cancelled'})