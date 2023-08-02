import datetime
from urllib import request
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.forms import formset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import FormView
from django.db.models import Q

from database.forms.creation_forms import (ContributionForm, FileForm,
                                           WorkInfoForm)
from database.forms.source_creation_form import SourceForm
from database.models import (ContributionMusicalWork, GenreAsInStyle, GenreAsInType,
                             Instrument, MusicalWork, Part, Person, Section)


class CreationView(FormView):
    template_name = 'creation_form.html'
    success_url = "/"

    def get(self, request, *args, **kwargs):
        """
        Handles GET requests and instantiates blank versions of the form
        and the formsets.
        """
        if not request.user.has_perm('simssadb.creation_access'):
            return redirect('/')
        
        form = WorkInfoForm()
        contribution_forms = formset_factory(ContributionForm)
        return self.render_to_response(
                self.get_context_data(error_message=None,
                                      form=form,
                                      contribution_form=contribution_forms))

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests, instantiating a form instance and its inline
        formsets with the passed POST variables and then checking them for
        validity.
        """

        # The form expects a list of titles and people for each autocomplete widget, 
        # so it must be changed before validation. Must be done in the original POST data, 
        # not in the cleaned data (i.e. not by overriding clean) nor in form_valid - an error will be thrown.
        post_data = request.POST.copy() # to make it mutable
        title = request.POST.get('title_from_db')
        if not title == None:
            post_data['title_from_db'] = [title]
        else:
            post_data['title_from_db'] = None
        key = 1
        while(request.POST.get(f'form-0-person_from_db_{key}') is not None):  
            print(f'fetching key {key}: ' + request.POST.get(f'form-0-person_from_db_{key}')) 
            post_data[f'form-0-person_from_db_{key}'] = request.POST.getlist(f'form-0-person_from_db_{key}')
            key = key + 1
        personcount = key
        request.POST = post_data
        
        # I'm getting the variant titles and sections before validation
        # because when the is_valid() method is called, the lists of
        # variant_titles and sections are transformed onto single values
        # TODO: check titles and sections for SQL injections etc
        variant_titles = request.POST.getlist('variant_title')
        sections = request.POST.getlist('sections')
        select_section = request.POST.getlist('select_section')
        variant_titles_from_db = request.POST.getlist('variant_titles_from_db')
        sections_from_db = request.POST.getlist('sections_from_db')
        select_section_from_db = request.POST.getlist('select_section_from_db')

        # Because the contribution form is duplicated with javascript and the duplicated widgets 
        # are not in the form definition, we need to manually add them to the cleaned data

        for key, value in request.POST.items():
            print(f'{key}: {value}')

        form = WorkInfoForm(request.POST)
        contribution_formset = formset_factory(ContributionForm)
        contribution_forms = contribution_formset(request.POST)
        if form.is_valid() and contribution_forms.is_valid():
            print('\nis valid called')
            print('form key/value pairs:')
            for key in form.cleaned_data:
                print(f'{key}: {form.cleaned_data[key]}')
            
            print('\ncontribution form key/value pairs:')
            i=1
            for contributionform in contribution_forms:
                print(f'cont form {i}')
                i=i+1
                for key in contributionform.cleaned_data:
                    print(f'{key}: {contributionform.cleaned_data[key]}')
            # Check that form is logically valid
            if (not form.cleaned_data['title_from_db'] and not form.cleaned_data['title']):
                print('work form invalid')
                return self.form_invalid(form, contribution_forms)
            # numform=1
            # for contribution_form in contribution_forms:
            #     if not request.POST.get(f'form-0-person_from_db_{numform}') and not \
            #     (contribution_form.cleaned_data[f'person_range_date_death_{numform}'] and \
            #     contribution_form.cleaned_data[f'person_range_date_birth_{numform}'] and \
            #     contribution_form.cleaned_data[f'person_given_name_{numform}']):
            #         print(f'contribution form {numform} invalid')
            #         return self.form_invalid(form, contribution_formset(request.POST))
            #     numform+=1

            form.cleaned_data['variant_titles'] = variant_titles
            form.cleaned_data['sections'] = sections
            form.cleaned_data['select_section'] = select_section
            form.cleaned_data['variant_titles_from_db'] = variant_titles_from_db
            form.cleaned_data['sections_from_db'] = sections_from_db
            form.cleaned_data['select_section_from_db'] = select_section_from_db
            form.cleaned_data['work_in_database'] = request.POST.get('work_not_in_database') == None
            form.cleaned_data['style_in_database'] = request.POST.get('style_not_in_database') == None
            form.cleaned_data['type_in_database'] = request.POST.get('type_not_in_database') == None
            for i in range(1,personcount): 
                form.cleaned_data[f'person_in_database_{i}'] = request.POST.get(f'person_not_in_database_{i}') == None
                form.cleaned_data[f'person_from_db_{i}'] = request.POST.get(f'form-0-person_from_db_{i}')
                form.cleaned_data[f'person_given_name_{i}'] = request.POST.get(f'form-0-person_given_name_{i}')
                form.cleaned_data[f'person_surname_{i}'] = request.POST.get(f'form-0-person_surname_{i}')
                form.cleaned_data[f'person_range_date_birth_{i}'] = request.POST.get(f'form-0-person_range_date_birth_{i}')
                form.cleaned_data[f'person_range_date_death_{i}'] = request.POST.get(f'form-0-person_range_date_death_{i}')
                form.cleaned_data[f'role_{i}'] = request.POST.get(f'form-0-role_{i}')
                form.cleaned_data[f'certainty_of_attribution_{i}'] = request.POST.get(f'form-0-certainty_of_attribution_{i}')
                form.cleaned_data[f'location_{i}'] = request.POST.get(f'form-0-location_{i}')
                form.cleaned_data[f'date_{i}'] = request.POST.get(f'form-0-date_{i}')
            return self.form_valid(form, contribution_forms, request)
        else:
            print('field is missing')
            return self.form_invalid(form, contribution_forms)
    

    def form_valid(self, form, contribution_forms, request):
        """
        Called if all forms are valid.
        """
        print('\nForm valid')
        print('form key/value pairs:')
        for key in form.cleaned_data:
            print(f'{key}: {form.cleaned_data[key]}')
        
        print('\ncontribution form key/value pairs:')
        i=1
        for contributionform in contribution_forms:
            print(f'cont form {i}')
            i=i+1
            for key in contributionform.cleaned_data:
                print(f'{key}: {contributionform.cleaned_data[key]}')
        styles = form.cleaned_data['genre_as_in_style']
        types = form.cleaned_data['genre_as_in_type']
        instruments = form.cleaned_data['instruments']
        sacred_or_secular = form.cleaned_data['sacred_or_secular']
        if not sacred_or_secular:
            sacred_or_secular = None
        if form.cleaned_data['work_in_database'] == True:
            work = form.cleaned_data['title_from_db'].first()
            variant_titles = form.cleaned_data['variant_titles_from_db']
            sections = form.cleaned_data['sections_from_db']
            section_titles = form.cleaned_data['select_section_from_db']
            if len(variant_titles) != 0:
                # Remove repeats regardless of case
                for variant_title in variant_titles:
                    lower_variant_title = variant_title.lower()
                    if lower_variant_title in [title.lower() for title in work.variant_titles]:
                        variant_titles.remove(variant_title)
                work.variant_titles = variant_titles + work.variant_titles
            work.save()
        else:
            title = form.cleaned_data['title']
            variant_titles = form.cleaned_data['variant_titles']
            sections = form.cleaned_data['sections']
            section_titles = form.cleaned_data['select_section']
            titles = [title] 
            if len(variant_titles) != 0:
                for variant_title in variant_titles:  
                    titles.append(variant_title) if not len(variant_title) == 0 else None
            work = MusicalWork(variant_titles=titles,
                            sacred_or_secular=sacred_or_secular)
            work.save()
            work.genres_as_in_style.set(styles)
            work.genres_as_in_type.set(types)
            work.save()            

        # Create sections
        print(len(sections))
        for i in range(len(sections)):
            print('i:  '+ str(i))
            print(sections)
            print(section_titles)
            if sections[i] == '':
                continue
            count = section_titles[i]
            entry = sections[i]
            section = Section(title=entry, musical_work=work)
            section.save()
            section.ordering = int(count)
            section.save()
            # Create parts for each section
            for instrument in instruments:
                part = Part(written_for=instrument, section=section)
                part.save()

        # Create contributions
        for contribution_form in contribution_forms:
            contribution_form_idx = 1
            while True:
                person = contribution_form.cleaned_data.get(f'person_from_db_{contribution_form_idx}')
                person_given_name = contribution_form.cleaned_data.get(f'person_given_name_{contribution_form_idx}')
                if not person and not person_given_name:
                    break

                if form.cleaned_data.get(f'person_in_database_{contribution_form_idx}'):
                    person = person.first()
                    print(f'Person {person} found in database')

                else:
                    try:
                        person_surname = contribution_form.cleaned_data.get(f'person_surname_{contribution_form_idx}')
                        person, created = Person.objects.get_or_create(
                                        given_name=person_given_name,
                                        surname=person_surname)    
                        range_date_birth = contribution_form.cleaned_data.get(f'person_range_date_birth_{contribution_form_idx}')
                        birth_date_from, birth_date_to = range_date_birth.lower, range_date_birth.upper
                        range_date_death = contribution_form.cleaned_data.get(f'person_range_date_death_{contribution_form_idx}')
                        death_date_from, death_date_to = range_date_death.lower, range_date_death.upper
                        person.range_date_birth = (birth_date_from, birth_date_to)
                        person.range_date_death = (death_date_from, death_date_to)
                        person.save() 
                        print(f'Created new person {person}')
                    except ValidationError as e:
                        print(f'Validation error {e}')
                        contribution_form_idx = contribution_form_idx+1
                        continue                    
        
                role = contribution_form.cleaned_data.get(f'role_{contribution_form_idx}')
                certainty = contribution_form.cleaned_data.get(f'certainty_of_attribution_{contribution_form_idx}')
                location = contribution_form.cleaned_data.get(f'location_{contribution_form_idx}')
                location = location.first() if location else None
                date = (date.lower, date.upper) if contribution_form.cleaned_data.get(f'date_{contribution_form_idx}') else None
                
                contribution = ContributionMusicalWork(person=person,
                                            role=role,
                                            certainty_of_attribution=certainty,
                                            date_range_year_only=date,
                                            location=location,
                                            contributed_to_work=work)
                contribution.save()
                print("Created new contribution")
                contribution_form_idx += 1

        request.session['work_id'] = work.id
        return HttpResponseRedirect('/file-create/')

    def form_invalid(self, form, contribution_forms):
        """
        Called if a form is invalid. Re-renders the context data with the
        data-filled forms and errors.
        """
        print('\nInvalid cleaned data:')
        print(form.errors)
        for key in form.cleaned_data:
            print(f'{key}: {form.cleaned_data.get(key)}')
        for contribution_form in contribution_forms:
            print(contribution_form.errors)
            for key in contribution_form.cleaned_data:
                print(f'{key}: {contribution_form.cleaned_data.get(key)}')
        error_message = "Please correct the form before resubmitting. All fields marked with * are required, unless the field is grayed out. For date ranges, if the date is known, you may enter it in a single box."
        return self.render_to_response(
            self.get_context_data(error_message=error_message,
                                  form=form,
                                  contribution_form=contribution_forms))
    

