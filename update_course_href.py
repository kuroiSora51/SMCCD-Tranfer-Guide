import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stg.settings')
django.setup()

from guide.models import Course  


def main():
   
  
    for course in Course.objects.all():
        slice = len("https://webschedule.smccd.edu/course/202")
        course.href = f"{course.href[0:slice]}6{course.href[slice+1:]}"
        course.save()
    


if __name__ == '__main__':
    main()
