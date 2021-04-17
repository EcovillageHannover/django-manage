from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from impersonate.admin import UserAdminImpersonateMixin
from account.models import GroupProfile, UserProfile

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profil'

class NewUserAdmin(UserAdminImpersonateMixin, UserAdmin):
    open_new_window = True
    inlines = (UserProfileInline, )


admin.site.unregister(User)
admin.site.register(User, NewUserAdmin)

class GroupProfileInline(admin.StackedInline):
    model = GroupProfile
    can_delete = False
    verbose_name_plural = 'Profil'
    fk_name = 'group'

class NewGroupAdmin(GroupAdmin):
    inlines = (GroupProfileInline, )

admin.site.unregister(Group)
admin.site.register(Group, NewGroupAdmin)
