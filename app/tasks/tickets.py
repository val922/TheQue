from sqlalchemy.sql import not_

from app.tasks.base import Task
from app.database import Serial, Display_store, Aliases
from app.middleware import gTTs
from app.utils import log_error, create_aliternative_db
from app.helpers import get_tts_safely


class CacheTicketsAnnouncements(Task):
    def __init__(self, app, interval=5, limit=30):
        ''' Task to cache tickets text-to-speech announcement audio files.

        Parameters
        ----------
            app: Flask app
            interval: int
                duration of sleep between iterations in seconds
            limit: int
                limit of tickets to processes each iteration.
        '''
        super().__init__(app)
        self.app = app
        self.interval = interval
        self.limit = limit
        self.cached = []
        self.tts_texts = get_tts_safely()
        self.session, self.db = create_aliternative_db(self.app.config.get('DB_NAME'))

    def format_announcement_text(self, ticket, aliases, language, show_prefix):
        ''' Helper to format text-to-speech text.

        Parameters
        ----------
            ticket: Serial record
            aliases: Aliases record
            language: str
                language of text-to-speech to produce
            show_prefix: bool
                include the office prefix in the announcement

        Returns
        -------
            String of formated text-to-speech text ready to use.
        '''
        with self.app.app_context():
            office = ticket.office
            prefix = office.prefix if show_prefix else ''
            office_text = f'{prefix}{office.name}'
            tts_text = self.tts_texts\
                           .get(language, {})\
                           .get('message')

            if language.startswith('en'):
                tts_text = tts_text.format(aliases.office)

            return f'{ticket.display_text}{tts_text}{office_text}'

    def run(self):
        @self.execution_loop()
        def main():
            display_settings = self.session.query(Display_store).first()

            if display_settings.announce != 'false':
                aliases = Aliases.query.first()
                languages = display_settings.announce.split(',')
                tickets_to_remove = self.session\
                                        .query(Serial)\
                                        .filter(Serial.p == True,
                                                Serial.number.in_(self.cached))
                tickets_to_cache = self.session\
                                       .query(Serial)\
                                       .filter(Serial.p == False,
                                               Serial.number != 100,
                                               not_(Serial.number.in_(self.cached)))\
                                       .order_by(Serial.timestamp)\
                                       .limit(self.limit)

                @self.none_blocking_loop(tickets_to_cache)
                def cache_tickets(ticket):
                    successes = []

                    @self.none_blocking_loop(languages)
                    def loop_languages(language):
                        try:
                            gTTs.say(language,
                                     self.format_announcement_text(ticket,
                                                                   aliases,
                                                                   language,
                                                                   display_settings.prefix))
                            successes.append(language)
                        except Exception as exception:
                            log_error(exception, quit=self.quiet)

                    if successes:
                        self.cached.append(ticket.number)
                        self.log(f'Cached TTS {ticket.number}')

                @self.none_blocking_loop(tickets_to_remove)
                def remove_processed_tickets_from_cache(ticket):
                    self.cached.remove(ticket.number)

            # NOTE: cache stack is adhereing to the limit to avoid overflow
            self.cached = self.cached[:self.limit]
