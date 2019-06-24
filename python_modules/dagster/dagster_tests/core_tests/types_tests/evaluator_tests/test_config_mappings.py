# pylint: disable=no-value-for-parameter

import pytest

from dagster import (
    composite_solid,
    execute_pipeline,
    lambda_solid,
    pipeline,
    solid,
    ConfigMapping,
    Field,
    InputDefinition,
    Int,
    PipelineConfigEvaluationError,
    Result,
    String,
)

# have to use "pipe" solid since "result_for_solid" doesnt work with composite mappings
@lambda_solid(inputs=[InputDefinition('input_str')])
def pipe(input_str):
    return input_str


@solid(config_field=Field(String, is_optional=True))
def scalar_config_solid(context):
    yield Result(context.solid_config)


@composite_solid(
    config_mapping=ConfigMapping(
        config={'override_str': Field(String)},
        config_mapping_fn=lambda cfg: {'scalar_config_solid': {'config': cfg['override_str']}},
    )
)
def wrap():
    return scalar_config_solid()


def test_multiple_overrides_pipeline():
    def nesting_config_mapping_fn(cfg):
        return {'wrap': {'config': {'override_str': cfg['nesting_override']}}}

    @composite_solid(
        config_mapping=ConfigMapping(
            config={'nesting_override': Field(String)}, config_mapping_fn=nesting_config_mapping_fn
        )
    )
    def nesting_wrap():
        return wrap()

    @pipeline
    def wrap_pipeline():
        return nesting_wrap.alias('outer_wrap')()

    result = execute_pipeline(
        wrap_pipeline,
        {
            'solids': {'outer_wrap': {'config': {'nesting_override': 'blah'}}},
            'loggers': {'console': {'config': {'log_level': 'ERROR'}}},
        },
    )

    output_event = [e for e in result.step_event_list if e.event_type_value == 'STEP_OUTPUT'][0]
    assert output_event.event_specific_data.value_repr == "'blah'"


def test_good_override():
    @pipeline
    def wrap_pipeline():
        return wrap.alias('do_stuff')()

    result = execute_pipeline(
        wrap_pipeline,
        {
            'solids': {'do_stuff': {'config': {'override_str': 'override'}}},
            'loggers': {'console': {'config': {'log_level': 'ERROR'}}},
        },
    )

    assert result.success


def test_missing_config():
    @pipeline
    def wrap_pipeline():
        return wrap.alias('do_stuff')()

    with pytest.raises(PipelineConfigEvaluationError) as exc_info:
        execute_pipeline(wrap_pipeline)

    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].message == (
        'Missing required field "solids" at document config root. Available Fields: '
        '''"['execution', 'expectations', 'loggers', 'resources', 'solids', 'storage']".'''
    )

    with pytest.raises(PipelineConfigEvaluationError) as exc_info:
        execute_pipeline(wrap_pipeline, {})

    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].message == (
        'Missing required field "solids" at document config root. Available Fields: '
        '''"['execution', 'expectations', 'loggers', 'resources', 'solids', 'storage']".'''
    )

    with pytest.raises(PipelineConfigEvaluationError) as exc_info:
        execute_pipeline(wrap_pipeline, {'solids': {}})

    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].message == (
        'Missing required field "do_stuff" at path root:solids Available Fields: '
        '''"['do_stuff']".'''
    )

    with pytest.raises(PipelineConfigEvaluationError) as exc_info:
        execute_pipeline(wrap_pipeline, {'solids': {'do_stuff': {}}})

    assert len(exc_info.value.errors) == 1
    assert (
        exc_info.value.errors[0].message
        == 'Missing required field "config" at path root:solids:do_stuff Available Fields: '
        '"[\'config\', \'outputs\']".'
    )

    with pytest.raises(PipelineConfigEvaluationError) as exc_info:
        execute_pipeline(wrap_pipeline, {'solids': {'do_stuff': {'config': {}}}})

    assert len(exc_info.value.errors) == 1
    assert (
        exc_info.value.errors[0].message
        == 'Missing required field "override_str" at path root:solids:do_stuff:config Available '
        'Fields: "[\'override_str\']".'
    )


def test_bad_override():
    @composite_solid(
        config_mapping=ConfigMapping(
            config={'does_not_matter': Field(String)},
            config_mapping_fn=lambda _: {'scalar_config_solid': {'config': 1234}},
        )
    )
    def bad_wrap():
        return scalar_config_solid()

    @pipeline
    def wrap_pipeline():
        return bad_wrap.alias('do_stuff')()

    with pytest.raises(PipelineConfigEvaluationError) as exc_info:
        execute_pipeline(
            wrap_pipeline,
            {
                'solids': {'do_stuff': {'config': {'does_not_matter': 'blah'}}},
                'loggers': {'console': {'config': {'log_level': 'ERROR'}}},
            },
        )

    assert len(exc_info.value.errors) == 1

    assert exc_info.value.errors[0].message == (
        '''Config override mapping function defined by solid do_stuff from definition bad_wrap at'''
        ''' path root:solids:do_stuff caused error: Value at path '''
        '''root:scalar_config_solid:config is not valid. Expected "String"'''
    )


def test_raises_fn_override():
    def raises_config_mapping_fn(_):
        assert 0

    @composite_solid(
        config_mapping=ConfigMapping(
            config={'does_not_matter': Field(String)}, config_mapping_fn=raises_config_mapping_fn
        )
    )
    def bad_wrap():
        return scalar_config_solid()

    @pipeline
    def wrap_pipeline():
        return bad_wrap.alias('do_stuff')()

    with pytest.raises(PipelineConfigEvaluationError) as exc_info:
        execute_pipeline(
            wrap_pipeline,
            {
                'solids': {'do_stuff': {'config': {'does_not_matter': 'foo'}}},
                'loggers': {'console': {'config': {'log_level': 'ERROR'}}},
            },
        )

    assert len(exc_info.value.errors) == 1
    assert (
        'Exception occurred during execution of user config mapping function '
        'raises_config_mapping_fn defined by solid do_stuff from definition bad_wrap at path '
        'root:solids:do_stuff'
    ) in exc_info.value.errors[0].message
    assert 'AssertionError: assert 0' in exc_info.value.errors[0].message


def test_composite_config_field():
    @solid(config={'inner': Field(String)})
    def inner_solid(context):
        return context.solid_config['inner']

    @composite_solid(
        config_mapping=ConfigMapping(
            config={'override': Field(Int)},
            config_mapping_fn=lambda cfg: {
                'inner_solid': {'config': {'inner': str(cfg['override'])}}
            },
        )
    )
    def test():
        return inner_solid()

    @pipeline
    def test_pipeline():
        return test()

    assert execute_pipeline(
        test_pipeline, {'solids': {'test': {'config': {'override': 5}}}}
    ).success


def test_nested_with_inputs():
    @solid(inputs=[InputDefinition('some_input', String)], config={'basic_key': Field(String)})
    def basic(context, some_input):
        yield Result(context.solid_config['basic_key'] + ' - ' + some_input)

    @composite_solid(
        inputs=[InputDefinition('some_input', String)],
        config_mapping=ConfigMapping(
            config_mapping_fn=lambda cfg: {
                'basic': {'config': {'basic_key': 'override.' + cfg['inner_first']}}
            },
            config={'inner_first': Field(String)},
        ),
    )
    def inner_wrap(some_input):
        return basic(some_input)

    def outer_wrap_fn(cfg):
        return {
            'inner_wrap': {
                'inputs': {'some_input': {'value': 'foobar'}},
                'config': {'inner_first': cfg['outer_first']},
            }
        }

    @composite_solid(
        config_mapping=ConfigMapping(
            config_mapping_fn=outer_wrap_fn, config={'outer_first': Field(String)}
        )
    )
    def outer_wrap():
        return inner_wrap()

    @pipeline(name='config_mapping')
    def config_mapping_pipeline():
        return pipe(outer_wrap())

    result = execute_pipeline(
        config_mapping_pipeline, {'solids': {'outer_wrap': {'config': {'outer_first': 'foo'}}}}
    )

    assert result.success
    assert result.result_for_solid('pipe').result_value() == 'override.foo - foobar'


def test_wrap_none_config_and_inputs():
    @solid(
        config={'config_field_a': Field(String), 'config_field_b': Field(String)},
        inputs=[InputDefinition('input_a', String), InputDefinition('input_b', String)],
    )
    def basic(context, input_a, input_b):
        res = '.'.join(
            [
                context.solid_config['config_field_a'],
                context.solid_config['config_field_b'],
                input_a,
                input_b,
            ]
        )
        yield Result(res)

    @composite_solid
    def wrap_none():
        return basic()

    @pipeline(name='config_mapping')
    def config_mapping_pipeline():
        return pipe(wrap_none())

    # Check all good
    result = execute_pipeline(
        config_mapping_pipeline,
        {
            'solids': {
                'wrap_none': {
                    'solids': {
                        'basic': {
                            'inputs': {
                                'input_a': {'value': 'set_input_a'},
                                'input_b': {'value': 'set_input_b'},
                            },
                            'config': {
                                'config_field_a': 'set_config_a',
                                'config_field_b': 'set_config_b',
                            },
                        }
                    }
                }
            }
        },
    )
    assert result.success
    assert (
        result.result_for_solid('pipe').result_value()
        == 'set_config_a.set_config_b.set_input_a.set_input_b'
    )

    # Check bad input override
    with pytest.raises(PipelineConfigEvaluationError) as exc_info:
        result = execute_pipeline(
            config_mapping_pipeline,
            {
                'solids': {
                    'wrap_none': {
                        'solids': {
                            'basic': {
                                'inputs': {
                                    'input_a': {'value': 1234},
                                    'input_b': {'value': 'set_input_b'},
                                },
                                'config': {
                                    'config_field_a': 'set_config_a',
                                    'config_field_b': 'set_config_b',
                                },
                            }
                        }
                    }
                }
            },
        )
    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].message == (
        'Value at path root:solids:wrap_none:solids:basic:inputs:input_a:value is not '
        'valid. Expected "String"'
    )

    # Check bad config override
    with pytest.raises(PipelineConfigEvaluationError) as exc_info:
        result = execute_pipeline(
            config_mapping_pipeline,
            {
                'solids': {
                    'wrap_none': {
                        'solids': {
                            'basic': {
                                'inputs': {
                                    'input_a': {'value': 'set_input_a'},
                                    'input_b': {'value': 'set_input_b'},
                                },
                                'config': {
                                    'config_field_a': 1234,
                                    'config_field_b': 'set_config_b',
                                },
                            }
                        }
                    }
                }
            },
        )
    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].message == (
        'Value at path root:solids:wrap_none:solids:basic:config:config_field_a is not valid. '
        'Expected "String"'
    )


def test_wrap_all_config_no_inputs():
    @solid(
        config={'config_field_a': Field(String), 'config_field_b': Field(String)},
        inputs=[InputDefinition('input_a', String), InputDefinition('input_b', String)],
    )
    def basic(context, input_a, input_b):
        res = '.'.join(
            [
                context.solid_config['config_field_a'],
                context.solid_config['config_field_b'],
                input_a,
                input_b,
            ]
        )
        yield Result(res)

    @composite_solid(
        inputs=[InputDefinition('input_a', String), InputDefinition('input_b', String)],
        config_mapping=ConfigMapping(
            config_mapping_fn=lambda cfg: {
                'basic': {
                    'config': {
                        'config_field_a': cfg['config_field_a'],
                        'config_field_b': cfg['config_field_b'],
                    }
                }
            },
            config={'config_field_a': Field(String), 'config_field_b': Field(String)},
        ),
    )
    def wrap_all_config_no_inputs(input_a, input_b):
        return basic(input_a, input_b)

    @pipeline(name='config_mapping')
    def config_mapping_pipeline():
        return pipe(wrap_all_config_no_inputs())

    result = execute_pipeline(
        config_mapping_pipeline,
        {
            'solids': {
                'wrap_all_config_no_inputs': {
                    'config': {'config_field_a': 'override_a', 'config_field_b': 'override_b'},
                    'inputs': {
                        'input_a': {'value': 'set_input_a'},
                        'input_b': {'value': 'set_input_b'},
                    },
                }
            }
        },
    )
    assert result.success
    assert (
        result.result_for_solid('pipe').result_value()
        == 'override_a.override_b.set_input_a.set_input_b'
    )

    with pytest.raises(PipelineConfigEvaluationError) as exc_info:
        result = execute_pipeline(
            config_mapping_pipeline,
            {
                'solids': {
                    'wrap_all_config_no_inputs': {
                        'config': {'config_field_a': 1234, 'config_field_b': 'override_b'},
                        'inputs': {
                            'input_a': {'value': 'set_input_a'},
                            'input_b': {'value': 'set_input_b'},
                        },
                    }
                }
            },
        )
    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].message == (
        'Value at path root:solids:wrap_all_config_no_inputs:config:config_field_a is not valid. '
        'Expected "String"'
    )

    with pytest.raises(PipelineConfigEvaluationError) as exc_info:
        result = execute_pipeline(
            config_mapping_pipeline,
            {
                'solids': {
                    'wrap_all_config_no_inputs': {
                        'config': {'config_field_a': 'override_a', 'config_field_b': 'override_b'},
                        'inputs': {'input_a': {'value': 1234}, 'input_b': {'value': 'set_input_b'}},
                    }
                }
            },
        )
    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].message == (
        'Value at path root:solids:wrap_all_config_no_inputs:inputs:input_a:value is not valid.'
        ' Expected "String"'
    )


def test_wrap_all_config_one_input():
    @solid(
        config={'config_field_a': Field(String), 'config_field_b': Field(String)},
        inputs=[InputDefinition('input_a', String), InputDefinition('input_b', String)],
    )
    def basic(context, input_a, input_b):
        res = '.'.join(
            [
                context.solid_config['config_field_a'],
                context.solid_config['config_field_b'],
                input_a,
                input_b,
            ]
        )
        yield Result(res)

    @composite_solid(
        inputs=[InputDefinition('input_a', String)],
        config_mapping=ConfigMapping(
            config_mapping_fn=lambda cfg: {
                'basic': {
                    'config': {
                        'config_field_a': cfg['config_field_a'],
                        'config_field_b': cfg['config_field_b'],
                    },
                    'inputs': {'input_b': {'value': 'set_input_b'}},
                }
            },
            config={'config_field_a': Field(String), 'config_field_b': Field(String)},
        ),
    )
    def wrap_all_config_one_input(input_a):
        return basic(input_a)

    @pipeline(name='config_mapping')
    def config_mapping_pipeline():
        return pipe(wrap_all_config_one_input())

    result = execute_pipeline(
        config_mapping_pipeline,
        {
            'solids': {
                'wrap_all_config_one_input': {
                    'config': {'config_field_a': 'override_a', 'config_field_b': 'override_b'},
                    'inputs': {'input_a': {'value': 'set_input_a'}},
                }
            }
        },
    )
    assert result.success
    assert (
        result.result_for_solid('pipe').result_value()
        == 'override_a.override_b.set_input_a.set_input_b'
    )

    with pytest.raises(PipelineConfigEvaluationError) as exc_info:
        result = execute_pipeline(
            config_mapping_pipeline,
            {
                'solids': {
                    'wrap_all_config_one_input': {
                        'config': {'config_field_a': 1234, 'config_field_b': 'override_b'},
                        'inputs': {'input_a': {'value': 'set_input_a'}},
                    }
                }
            },
        )
    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].message == (
        'Value at path root:solids:wrap_all_config_one_input:config:config_field_a is not valid. '
        'Expected "String"'
    )

    with pytest.raises(PipelineConfigEvaluationError) as exc_info:
        result = execute_pipeline(
            config_mapping_pipeline,
            {
                'solids': {
                    'wrap_all_config_one_input': {
                        'config': {'config_field_a': 'override_a', 'config_field_b': 'override_b'},
                        'inputs': {'input_a': {'value': 1234}},
                    }
                }
            },
        )
    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].message == (
        'Value at path root:solids:wrap_all_config_one_input:inputs:input_a:value is not valid. '
        'Expected "String"'
    )


def test_wrap_all_config_and_inputs():
    @solid(
        config={'config_field_a': Field(String), 'config_field_b': Field(String)},
        inputs=[InputDefinition('input_a', String), InputDefinition('input_b', String)],
    )
    def basic(context, input_a, input_b):
        res = '.'.join(
            [
                context.solid_config['config_field_a'],
                context.solid_config['config_field_b'],
                input_a,
                input_b,
            ]
        )
        yield Result(res)

    @composite_solid(
        config_mapping=ConfigMapping(
            config_mapping_fn=lambda cfg: {
                'basic': {
                    'config': {
                        'config_field_a': cfg['config_field_a'],
                        'config_field_b': cfg['config_field_b'],
                    },
                    'inputs': {
                        'input_a': {'value': 'override_input_a'},
                        'input_b': {'value': 'override_input_b'},
                    },
                }
            },
            config={'config_field_a': Field(String), 'config_field_b': Field(String)},
        )
    )
    def wrap_all():
        return basic()

    @pipeline(name='config_mapping')
    def config_mapping_pipeline():
        return pipe(wrap_all())

    result = execute_pipeline(
        config_mapping_pipeline,
        {
            'solids': {
                'wrap_all': {
                    'config': {'config_field_a': 'override_a', 'config_field_b': 'override_b'}
                }
            }
        },
    )

    assert result.success
    assert (
        result.result_for_solid('pipe').result_value()
        == 'override_a.override_b.override_input_a.override_input_b'
    )

    with pytest.raises(PipelineConfigEvaluationError) as exc_info:
        result = execute_pipeline(
            config_mapping_pipeline,
            {
                'solids': {
                    'wrap_all': {
                        'config': {
                            'config_field_a': 'override_a',
                            'this_key_doesnt_exist': 'override_b',
                        }
                    }
                }
            },
        )

    assert len(exc_info.value.errors) == 2
    assert exc_info.value.errors[0].message == (
        'Field "this_key_doesnt_exist" is not defined at path root:solids:wrap_all:config '
        'Expected: "{ config_field_a: String config_field_b: String }"'
    )

    assert (
        exc_info.value.errors[1].message
        == 'Missing required field "config_field_b" at path root:solids:wrap_all:config '
        'Available Fields: "[\'config_field_a\', \'config_field_b\']".'
    )