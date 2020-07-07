from flask import url_for, flash, request, render_template, redirect
from flask import Blueprint, session
from flask_login import current_user, login_required

import app.forms as forms
import app.database as data
from app.middleware import db
from app.utils import ids
from app.helpers import (reject_operator, reject_no_offices, is_operator, is_office_operator,
                         is_common_task_operator, reject_setting)


manage_app = Blueprint('manage_app', __name__)


@manage_app.route('/manage')
@login_required
def manage():
    ''' management welcome screen. '''
    if is_operator() and not data.Settings.get().single_row:
        operator = data.Operators.get(current_user.id)

        flash('Error: operators are not allowed to access the page ', 'danger')
        return redirect(url_for('manage_app.offices', o_id=operator.office_id))

    return render_template('manage.html',
                           page_title='Management',
                           navbar='#snb1',
                           ooid=0,  # NOTE: filler to collapse specific office
                           serial=data.Serial.query.filter(data.Serial.number != 100),
                           offices=data.Office.query,
                           operators=data.Operators.query,
                           tasks=data.Task.query)


@manage_app.route('/all_offices')
@login_required
@reject_operator
def all_offices():
    ''' lists all offices. '''
    page = request.args.get('page', 1, type=int)
    tickets = data.Serial.query.filter(data.Serial.number != 100)\
                               .order_by(data.Serial.p, data.Serial.timestamp.desc())
    pagination = tickets.paginate(page, per_page=10, error_out=False)
    last_ticket_pulled = tickets.filter_by(p=True).first()
    last_ticket_office = last_ticket_pulled and data.Office.query\
                                                    .filter_by(id=last_ticket_pulled.office_id)\
                                                    .first()

    return render_template('all_offices.html',
                           officesp=pagination.items,
                           pagination=pagination,
                           len=len,
                           page_title='All Offices',
                           serial=data.Serial.query.filter(data.Serial.number != 100),
                           offices=data.Office.query,
                           tasks=data.Task.query,
                           users=data.User.query,
                           operators=data.Operators.query,
                           navbar='#snb1',
                           hash='#da2',
                           last_ticket_pulled=last_ticket_pulled,
                           last_ticket_office=last_ticket_office)


@manage_app.route('/offices/<int:o_id>', methods=['GET', 'POST'])
@login_required
@reject_setting('single_row', True)
def offices(o_id):
    ''' view and update an office. '''
    office = data.Office.get(o_id)

    if office is None:
        flash('Error: wrong entry, something went wrong', 'danger')
        return redirect(url_for('core.root'))

    if is_operator() and not is_office_operator(o_id):
        flash('Error: operators are not allowed to access the page ', 'danger')
        return redirect(url_for('core.root'))

    form = forms.Offices_a(upd=office.prefix, defLang=session.get('lang'))
    page = request.args.get('page', 1, type=int)
    tickets = data.Serial.all_office_tickets(o_id)
    last_ticket_pulled = tickets.filter_by(p=True).first()
    pagination = tickets.paginate(page, per_page=10, error_out=False)

    if form.validate_on_submit():
        # NOTE: Check if the office's name is already used
        for matching_office in data.Office.query.filter_by(name=form.name.data):
            if matching_office.id != o_id:
                flash('Error: name is used by another one, choose another name', 'danger')
                return redirect(url_for('manage_app.offices', o_id=o_id))

        office.name = form.name.data
        office.prefix = form.prefix.data.upper()
        db.session.commit()
        flash('Notice: office has been updated. ', 'info')
        return redirect(url_for('manage_app.offices', o_id=o_id))

    form.name.data = office.name
    form.prefix.data = office.prefix.upper()

    return render_template('offices.html',
                           form=form,
                           officesp=pagination.items,
                           pagination=pagination,
                           page_title='Office : ' + office.prefix + str(office.name),
                           o_id=o_id,
                           ooid=office,
                           len=len,
                           serial=tickets,
                           offices=data.Office.query,
                           tasks=data.Task.query,
                           users=data.User.query,
                           operators=data.Operators.query,
                           navbar='#snb1',
                           dropdown='#dropdown-lvl' + str(o_id),
                           hash='#t1' + str(o_id),
                           last_ticket_pulled=last_ticket_pulled)


@manage_app.route('/office_a', methods=['GET', 'POST'])
@login_required
@reject_operator
@reject_setting('single_row', True)
def office_a():
    ''' add an office. '''
    form = forms.Offices_a(defLang=session.get('lang'))

    if form.validate_on_submit():
        if data.Office.query.filter_by(name=form.name.data).first():
            flash('Error: name is used by another one, choose another name', 'danger')
            return redirect(url_for('manage_app.all_offices'))

        db.session.add(data.Office(form.name.data, form.prefix.data.upper()))
        db.session.commit()
        flash('Notice: new office been added . ', 'info')
        return redirect(url_for('manage_app.all_offices'))

    return render_template('office_add.html',
                           form=form,
                           page_title='Adding new office',
                           offices=data.Office.query,
                           tasks=data.Task.query,
                           operators=data.Operators.query,
                           navbar='#snb1',
                           hash='#da3',
                           serial=data.Serial.query.filter(data.Serial.number != 100))


@manage_app.route('/office_d/<int:o_id>')
@login_required
@reject_operator
@reject_setting('single_row', True)
def office_d(o_id):
    ''' delete office and its belongings. '''
    office = data.Office.get(o_id)

    if not office:
        flash('Error: wrong entry, something went wrong', 'danger')
        return redirect(url_for('manage_app.offices', o_id=o_id))

    if office.tickets.count():
        flash('Error: you must reset it, before you delete it ', 'danger')
        return redirect(url_for('manage_app.offices', o_id=o_id))

    office.delete_all()
    flash('Notice: office and its all tasks been deleted ', 'info')
    return redirect(url_for('manage_app.all_offices'))


@manage_app.route('/office_da')
@login_required
@reject_operator
@reject_no_offices
@reject_setting('single_row', True)
def office_da():
    ''' delete all offices and their belongings.'''
    if data.Serial.query.filter(data.Serial.number != 100).count():
        flash('Error: you must reset it, before you delete it ', 'danger')
        return redirect(url_for('manage_app.all_offices'))

    data.Serial.query.delete()
    data.Task.query.delete()
    data.Office.query.delete()
    db.session.commit()
    flash('Notice: office and its all tasks been deleted ', 'info')
    return redirect(url_for('manage_app.all_offices'))


@manage_app.route('/search', methods=['GET', 'POST'])
@login_required
@reject_operator
def search():
    ''' search for tickets. '''
    search_kwargs = {}
    first_time = not bool(request.args.get('page', default=0, type=int))
    form = forms.Search_s(session.get('lang')) if first_time else search.form
    base_template_arguments = dict(form=form, page_title='Tickets search', offices=data.Office.query,
                                   tasks=data.Task.query, users=data.User.query, len=len,
                                   operators=data.Operators.query, navbar='#snb1', hash='#da1',
                                   serial=data.Serial.query.filter(data.Serial.number != 100))

    # NOTE: storing the first form submitted as an endpoint attr instead of a global variable
    if first_time:
        setattr(search, 'form', form)

    if form.validate_on_submit() or not first_time:

        for form_data, keyword_argument in [
            (form.number.data, {'number': form.number.data}),
            (form.date.data, {'date': form.date.data and form.date.data.strftime('%Y-%m-%d')}),
            (form.tl.data, {'office_id': form.tl.data})
        ]:
            if form_data and str(form_data).strip():
                search_kwargs.update(keyword_argument)

        if not search_kwargs:
            flash('Error: fault in search parameters', 'danger')
            return redirect(url_for('manage_app.search'))

        tickets_found = data.Serial.query.filter(data.Serial.number != 100)\
                                         .filter_by(**search_kwargs)

        if not tickets_found.first():
            flash('Notice: Sorry, no matching results were found ', 'info')
            return redirect(url_for('manage_app.search'))

        page = request.args.get('page', 1, type=int)
        pagination = tickets_found.order_by(data.Serial.timestamp.desc())\
                                  .paginate(page, per_page=10, error_out=False)

        return render_template('search_r.html', serials=tickets_found, pagination=pagination,
                               serialsp=pagination.items, **base_template_arguments)

    return render_template('search.html', **base_template_arguments)


@manage_app.route('/task/<int:o_id>', methods=['POST', 'GET'], defaults={'ofc_id': None})
@manage_app.route('/task/<int:o_id>/<int:ofc_id>', methods=['POST', 'GET'])
@login_required
@reject_setting('single_row', True)
def task(o_id, ofc_id=None):
    ''' view specific task. '''
    task = data.Task.get(o_id)

    if task is None:
        flash('Error: wrong entry, something went wrong', 'danger')
        return redirect(url_for('core.root'))

    form = forms.Task_a(session.get('lang'), task.common)

    if is_operator() and not is_common_task_operator(task.id):
        flash('Error: operators are not allowed to access the page ', 'danger')
        return redirect(url_for('core.root'))

    page = request.args.get('page', 1, type=int)
    tickets = data.Serial.all_task_tickets(ofc_id, task.id)
    last_ticket_pulled = tickets.filter_by(p=True).first()
    pagination = tickets.paginate(page, per_page=10, error_out=False)

    if form.validate_on_submit():
        if data.Task.query.filter_by(name=form.name.data).count() > 1:
            flash('Error: name is used by another one, choose another name', 'danger')
            return redirect(url_for('manage_app.task', o_id=o_id, ofc_id=ofc_id))

        task = data.Task.get(o_id)
        task.name = form.name.data

        if task.common:
            checked_offices = [o for o in data.Office.query.all() if form[f'check{o.id}'].data]
            removed_offices = [o for o in task.offices if o.id not in ids(checked_offices)]
            to_add_offices = [o for o in checked_offices if o.id not in ids(task.offices)]

            if not checked_offices:
                flash('Error: one office must be selected at least', 'danger')
                return redirect(url_for('manage_app.common_task_a'))

            for office in removed_offices:
                task.migrate_tickets(office, checked_offices[0])
                task.offices.remove(office)

            for office in to_add_offices:
                task.offices.append(office)

        db.session.commit()
        flash('Notice: task has been updated .', 'info')
        return redirect(url_for('manage_app.task', o_id=o_id, ofc_id=ofc_id))

    if not form.errors:
        form.name.data = task.name

        for office in task.offices:
            form[f'check{office.id}'].data = True

    if not ofc_id:
        # NOTE: sidebar collapse failsafe, just incase the office id wasn't passed
        ofc_id = task.offices[0].id

    return render_template('tasks.html',
                           form=form,
                           page_title='Task : ' + task.name,
                           tasksp=pagination.items,
                           pagination=pagination,
                           serial=tickets,
                           o_id=o_id,
                           ofc_id=ofc_id,
                           common=task.common,
                           len=len,
                           offices=data.Office.query,
                           tasks=data.Task.query,
                           users=data.User.query,
                           operators=data.Operators.query,
                           task=task,
                           navbar='#snb1',
                           dropdown='#dropdown-lvl%i' % ofc_id,  # dropdown a list of offices
                           hash='#tt%i%i' % (ofc_id, o_id),
                           last_ticket_pulled=last_ticket_pulled,
                           edit_task=len(task.offices) == 1 or not is_operator(),
                           office=data.Office.get(ofc_id))


@manage_app.route('/task_d/<int:t_id>', defaults={'ofc_id': None})
@manage_app.route('/task_d/<int:t_id>/<int:ofc_id>')
@login_required
@reject_setting('single_row', True)
def task_d(t_id, ofc_id=None):
    ''' to delete a task '''
    task = data.Task.get(t_id)

    if task is None:
        flash('Error: wrong entry, something went wrong', 'danger')
        return redirect(url_for('core.root'))

    if is_operator() and not is_common_task_operator(task.id):
        flash('Error: operators are not allowed to access the page ', 'danger')
        return redirect(url_for('core.root'))

    tickets = data.Serial.query.filter(data.Serial.task_id == t_id)

    if tickets.filter(data.Serial.number != 100).count() > 0:
        flash('Error: you must reset it, before you delete it ', 'danger')
        return redirect(url_for('manage_app.task', o_id=t_id, ofc_id=ofc_id))

    tickets.delete()
    db.session.delete(data.Task.get(t_id))
    db.session.commit()
    flash('Notice: task has been deleted .', 'info')
    return redirect(url_for('manage_app.offices', o_id=ofc_id) if ofc_id else url_for('manage_app.all_offices'))


@manage_app.route('/common_task_a', methods=['GET', 'POST'])
@login_required
@reject_operator
@reject_setting('single_row', True)
def common_task_a():
    ''' to add a common task '''
    if data.Office.query.count() <= 1:
        flash('Error: not enough offices exist to add a common task', 'danger')
        return redirect(url_for('manage_app.all_offices'))

    form = forms.Task_a(session.get('lang'), True)

    if form.validate_on_submit():
        task = data.Task(form.name.data)

        if data.Task.query.filter_by(name=form.name.data).first() is not None:
            flash('Error: name is used by another one, choose another name', 'danger')
            return redirect(url_for('manage_app.common_task_a'))

        offices_validation = [form[f'check{o.id}'].data for o in data.Office.query.all()]
        if len(offices_validation) > 0 and not any(offices_validation):
            flash('Error: one office must be selected at least', 'danger')
            return redirect(url_for('manage_app.common_task_a'))

        db.session.add(task)
        db.session.commit()

        for office in data.Office.query.all():
            if form['check%i' % office.id].data and office not in task.offices:
                task.offices.append(office)

        for office in task.offices:
            initial_ticket = data.Serial.query\
                                 .filter_by(office_id=office.id, number=100)\
                                 .first()

            if not initial_ticket:
                db.session.add(data.Serial(
                    office_id=office.id,
                    task_id=task.id,
                    p=True
                ))

        db.session.commit()
        flash('Notice: a common task has been added.', 'info')
        return redirect(url_for('manage_app.all_offices'))
    return render_template('task_add.html', form=form,
                           offices=data.Office.query,
                           serial=data.Serial.query.filter(data.Serial.number != 100),
                           tasks=data.Task.query,
                           operators=data.Operators.query,
                           navbar='#snb1', common=True,
                           page_title='Add a common task',
                           hash='#da6')


@manage_app.route('/task_a/<int:o_id>', methods=['GET', 'POST'])
@login_required
@reject_setting('single_row', True)
def task_a(o_id):
    ''' to add a task '''
    form = forms.Task_a(session.get('lang'))
    office = data.Office.get(o_id)

    if office is None:
        flash('Error: wrong entry, something went wrong', 'danger')
        return redirect(url_for('core.root'))

    if is_operator() and not is_office_operator(office.id):
        flash('Error: operators are not allowed to access the page ', 'danger')
        return redirect(url_for('core.root'))

    if form.validate_on_submit():
        if data.Task.query.filter_by(name=form.name.data).first() is not None:
            flash('Error: name is used by another one, choose another name', 'danger')
            return redirect(url_for('manage_app.task_a', o_id=o_id))

        task = data.Task(form.name.data)
        db.session.add(task)
        db.session.commit()

        if office.id not in ids(task.offices):
            task.offices.append(office)
            db.session.commit()

        initial_ticket = data.Serial.query.filter_by(task_id=task.id,
                                                     office_id=o_id,
                                                     number=100)\
                                          .first()

        if not initial_ticket:
            db.session.add(data.Serial(
                office_id=task.offices[0].id,
                task_id=task.id,
                p=True
            ))
            db.session.commit()

        flash('Notice: New task been added.', 'info')
        return redirect(url_for('manage_app.offices', o_id=o_id))
    return render_template('task_add.html', form=form,
                           offices=data.Office.query,
                           serial=data.Serial.query.filter(data.Serial.number != 100),
                           tasks=data.Task.query,
                           operators=data.Operators.query,
                           navbar='#snb1', common=False,
                           dropdown='#dropdown-lvl' + str(o_id),
                           hash='#t3' + str(o_id),
                           page_title='Add new task')
