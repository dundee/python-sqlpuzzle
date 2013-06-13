# -*- coding: utf-8 -*-

import six

import sqlpuzzle._libs.argsparser
import sqlpuzzle._libs.sqlvalue
import sqlpuzzle._libs.customsql
import sqlpuzzle._features.conditions


INNER_JOIN = 0
LEFT_JOIN = 1
RIGHT_JOIN = 2

JOIN_TYPES = {
    INNER_JOIN: 'JOIN',
    LEFT_JOIN: 'LEFT JOIN',
    RIGHT_JOIN: 'RIGHT JOIN',
}


class OnCondition(sqlpuzzle._features.conditions.Condition):
    def __str__(self):
        """Print part of query."""
        return '%s = %s' % (
            sqlpuzzle._libs.sqlvalue.SqlReference(self._column),
            sqlpuzzle._libs.sqlvalue.SqlReference(self._value),
        )

    def __eq__(self, other):
        """Are on codntions equivalent?"""
        return (
            (self._column == other._column and self._value == other._value) or
            (self._column == other._value and self._value == other._column)
        )


class OnConditions(sqlpuzzle._features.conditions.Conditions):
    def __init__(self):
        """Initialization of OnConditions."""
        super(OnConditions, self).__init__(OnCondition)
        self._separator_of_features = ' AND '


class Table(sqlpuzzle._features.Feature):
    def __init__(self, table=None, as_=None):
        """Initialization of Table."""
        super(Table, self).__init__()
        self._table = table
        self._as = as_
        self._joins = []

    def __str__(self):
        """Print part of query."""
        if self._as:
            table = '%s AS %s' % (
                sqlpuzzle._libs.sqlvalue.SqlReference(self._table),
                sqlpuzzle._libs.sqlvalue.SqlReference(self._as),
            )
        else:
            table = str(sqlpuzzle._libs.sqlvalue.SqlReference(self._table))

        if self._joins != []:
            if any([not join['ons'].is_set() for join in self._joins]):
                raise sqlpuzzle.exceptions.InvalidQueryException(
                    "You can't use join without on.")

            self.__minimize_joins()
            table = '%s %s' % (
                table,
                ' '.join([
                    '%s %s ON (%s)' % (
                        JOIN_TYPES[join['type']],
                        str(join['table']),
                        str(join['ons']),
                    ) for join in self._joins
                ])
            )

        return table

    def __eq__(self, other):
        """Are tables equivalent?"""
        return (
            self._table == other._table and
            self._as == other._as and
            self._joins == other._joins
        )

    def __minimize_joins(self):
        """
        Minimize of joins.
        Left/right and inner join of the same join is only inner join.
        """
        joins_group = []
        for join in self._joins:
            append_new = True
            for join_group in joins_group:
                if join_group[0]['table'] == join['table'] and join_group[0]['ons'] == join['ons']:
                    join_group.append(join)
                    append_new = False
                    break
            if append_new:
                joins_group.append([join])

        self._joins = []
        for joins in joins_group:
            if len(joins) > 1 and any(bool(join['type'] == INNER_JOIN) for join in joins):
                joins[0]['type'] = INNER_JOIN
                self._joins.append(joins[0])
            else:
                self._joins.extend(joins)

    def is_simple(self):
        """Is set table without join?"""
        return self._joins == []

    def join(self, arg, join_type=INNER_JOIN):
        """Join table."""
        if isinstance(arg, (list, tuple)) and len(arg) == 2:
            table = Table(*arg)
        elif isinstance(arg, dict) and len(arg) == 1:
            table = Table(*arg.popitem())
        elif isinstance(arg, six.string_types):
            table = Table(arg)
        else:
            raise sqlpuzzle.exceptions.InvalidArgumentException(
                'Invalid argument for join.')

        self._joins.append({
            'type': join_type,
            'table': table,
            'ons': OnConditions(),
        })

    def on(self, *args, **kwds):
        """Join on."""
        if self.is_simple():
            raise sqlpuzzle.exceptions.InvalidQueryException(
                "You can't set join without table.")

        self._joins[-1]['ons'].where(*args, **kwds)


class Tables(sqlpuzzle._features.Features):
    def last_table(self):
        """Get last table."""
        if self._features:
            return self._features[-1]
        raise sqlpuzzle.exceptions.SqlPuzzleException(
            'Tables doesn\'t set - there is no last table.')

    def is_simple(self):
        """Is set only one table without join?"""
        return len(self._features) == 1 and self._features[0].is_simple()

    def set(self, *args, **kwds):
        """Set tables."""
        args = [arg for arg in args if arg]

        allowed_data_types = sqlpuzzle._libs.argsparser.AllowedDataTypes().add(
            six.string_types + (sqlpuzzle._queries.select.Select, sqlpuzzle._queries.union.Union, sqlpuzzle._libs.customsql.CustomSql),
            six.string_types,
        ).add(
            sqlpuzzle._libs.customsql.CustomSql
        )

        for table, as_ in sqlpuzzle._libs.argsparser.parse_args_to_list_of_tuples(
            {
                'max_items': 2,
                'allow_dict': True,
                'allowed_data_types': allowed_data_types
            },
            *args,
            **kwds
        ):
            table = Table(table, as_)
            if table not in self:
                self.append_feature(table)

        return self

    def join(self, arg):
        """Join table."""
        return self.inner_join(arg)

    def inner_join(self, arg):
        """Inner join table."""
        if not self.is_set():
            raise sqlpuzzle.exceptions.InvalidQueryException(
                "You can't set join without table.")

        self.last_table().join(arg, INNER_JOIN)
        return self

    def left_join(self, arg):
        """Left join table."""
        if not self.is_set():
            raise sqlpuzzle.exceptions.InvalidQueryException(
                "You can't set join without table.")

        self.last_table().join(arg, LEFT_JOIN)
        return self

    def right_join(self, arg):
        """Right join table."""
        if not self.is_set():
            raise sqlpuzzle.exceptions.InvalidQueryException(
                "You can't set join without table.")

        self.last_table().join(arg, RIGHT_JOIN)
        return self

    def on(self, *args, **kwds):
        """Join on."""
        if not self.is_set():
            raise sqlpuzzle.exceptions.InvalidQueryException(
                "You can't set condition of join without table.")

        self.last_table().on(*args, **kwds)
        return self


class TablesForSelect(Tables):
    def __init__(self):
        """Initialization of TablesForSelect."""
        super(Tables, self).__init__()
        self._keyword_of_feature = 'FROM'
