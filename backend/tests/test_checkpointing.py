"""Checkpoint identity, data-only serialization, and authorization regression."""
import unittest
from unittest.mock import Mock, patch

from app.agents.checkpointing import (ContextSerializer, authorize_checkpoint,
    checkpoint_config, checkpoint_connection_string, checkpoint_thread_id)
from app.agents.execution_context import ExecutionContext, AgentOutput
from app.agents.graphs import build_single_graph, build_fixed_graph, build_adaptive_graph
from app.models.schemas import TaskExecutionMode
from app.security.rbac import AuthorizationError


class CheckpointTests(unittest.TestCase):
    def test_connection_protocols(self):
        for scheme in ('postgresql+psycopg', 'postgres', 'postgresql'):
            self.assertEqual(checkpoint_connection_string(scheme+'://host/db'), 'postgresql://host/db')
        with self.assertRaises(ValueError):
            checkpoint_connection_string('sqlite:///db')

    def test_identity_stable_collision_resistant_and_fail_closed(self):
        def identity(w, t):
            return checkpoint_thread_id(task_id=t, workspace_id=w)
        self.assertEqual(identity('a', 'b'), identity('a', 'b'))
        self.assertNotEqual(identity('a:b', 'c'), identity('a', 'b:c'))
        self.assertNotEqual(identity('a', 'b'), identity('b', 'b'))
        for w in (None, '', ' '):
            with self.assertRaises(AuthorizationError):
                identity(w, 't')
        with self.assertRaises(ValueError):
            identity('w', ' ')
        self.assertEqual(checkpoint_config(task_id='b', workspace_id='a')['configurable']['thread_id'], identity('a','b'))

    def test_context_and_nested_outputs_restore_typed_and_frozen(self):
        context = ExecutionContext(original_directive='goal', execution_mode=TaskExecutionMode.SINGLE).with_output('direct', 'answer')
        serde = ContextSerializer()
        result = serde.loads_typed(serde.dumps_typed({'context': context}))['context']
        self.assertEqual(result, context)
        self.assertIsInstance(result.prior_outputs[0], AgentOutput)
        with self.assertRaises(ValueError):
            result.original_directive = 'other'
        with self.assertRaises(ValueError):
            serde.loads_typed(('pickle', b'bad'))

    def test_authorization_checks_workspace_permission_and_task_visibility(self):
        repo = Mock()
        repo.get_for_tenant.return_value.workspace_id = 'w'
        with patch('app.agents.checkpointing.resolve_workspace_authorization') as resolve:
            authorize_checkpoint(repo, task_id='t',workspace_id='w',user_id='u')
            resolve.assert_called_once_with(repo, workspace_id='w', user_id='u')
            repo.get_for_tenant.return_value = None
            with self.assertRaises(AuthorizationError):
                authorize_checkpoint(repo,task_id='t',workspace_id='w',user_id='u')
        for missing in ('task_id','workspace_id','user_id'):
            identity = dict(task_id='t',workspace_id='w',user_id='u')
            identity[missing] = None
            with self.assertRaises(AuthorizationError):
                authorize_checkpoint(repo, **identity)

    def test_builders_accept_saver(self):
        saver = object()
        for build in (build_single_graph, build_fixed_graph, build_adaptive_graph):
            self.assertIs(build(checkpointer=saver).checkpointer, saver)

class SaverBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_foreign_threads_namespaces_and_global_listing_denied(self):
        from app.agents.checkpointing import AuthorizedPostgresSaver
        saver = AuthorizedPostgresSaver(Mock(), repository=Mock(),
            task_id='t',workspace_id='w',user_id='u')
        for config in (None, {'configurable': {'thread_id':'foreign'}},
                {'configurable': {'thread_id':saver.thread_id,'checkpoint_ns':'foreign'}}):
            with self.assertRaises(AuthorizationError):
                await saver.aget_tuple(config)
            with self.assertRaises(AuthorizationError):
                await saver.aput(config, {}, {}, {})
            with self.assertRaises(AuthorizationError):
                await saver.aput_writes(config, [], 'node')
            with self.assertRaises(AuthorizationError):
                async for _ in saver.alist(config):
                    pass
        with self.assertRaises(AuthorizationError):
            await saver.adelete_thread('foreign')
        with self.assertRaises(PermissionError):
            await saver.setup()

    async def test_every_operation_rechecks_revoked_membership(self):
        from app.agents.checkpointing import AuthorizedPostgresSaver
        saver = AuthorizedPostgresSaver(Mock(),repository=Mock(),
            task_id='t',workspace_id='w',user_id='u')
        config = checkpoint_config(task_id='t',workspace_id='w')
        with patch('app.agents.checkpointing.authorize_checkpoint', side_effect=AuthorizationError('revoked')) as auth:
            with self.assertRaises(AuthorizationError):
                await saver.aget_tuple(config)
            with self.assertRaises(AuthorizationError):
                await saver.aput(config,{}, {}, {})
            self.assertEqual(auth.call_count,2)
