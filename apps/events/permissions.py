from rest_framework import permissions


class IsProducerOrReadOnly(permissions.BasePermission):
    """
    - Lectura (GET/HEAD/OPTIONS): abierta a todos.
    - Escritura (POST/PUT/PATCH/DELETE): solo usuarios autenticados con is_producer=True.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        # 👇 Permitimos a productores Y admins (is_staff)
        return request.user.is_authenticated and (getattr(request.user, 'is_producer', False) or request.user.is_staff)


class IsEventOwner(permissions.BasePermission):
    """Solo el productor dueño del evento puede editarlo/borrarlo."""
    def has_object_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user == view.get_event_organizer() \
            if hasattr(view, 'get_event_organizer') else request.user == getattr(request, 'user', None)