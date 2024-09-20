from extras.scripts import Script, StringVar
from extras.models import Tag

class CreateIncrementalTag(Script):
    class Meta:
        name = "Create Incremental Tag"
        description = "Create a new tag with an incrementing numeral each time it is run"

    def run(self, data, commit):
        # Fetch existing tags to determine the next numeral
        existing_tags = Tag.objects.filter(name__startswith='tag')
        tag_numbers = [int(tag.name[3:]) for tag in existing_tags if tag.name[3:].isdigit()]
        next_number = max(tag_numbers, default=0) + 1

        # Create new tag
        new_tag_name = f'tag{next_number}'
        new_tag = Tag(name=new_tag_name)
        new_tag.save()

        self.log_success(f'Created new tag: {new_tag_name}')

# Save this script as create_incremental_tag.py in the appropriate directory
