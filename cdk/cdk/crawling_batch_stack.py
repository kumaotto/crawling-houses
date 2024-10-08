from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_ssm as ssm,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    aws_lambda_python_alpha as lambda_alpha,
)
from constructs import Construct


class CrawlingBatchStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, is_use_spreadsheet: bool, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        """
        DynamoDB
        """
        table = dynamodb.Table(
            self,
            "CrawlingPropertyCache",
            partition_key={"name": "PropertyID", "type": dynamodb.AttributeType.STRING},
            removal_policy=RemovalPolicy.DESTROY,
        )

        """
        Lambda
        """
        # Lambda Layer
        crawling_layer = lambda_alpha.PythonLayerVersion(
            self,
            "CrawlingModuleLayer",
            entry="lambda/layer/crawling_layer",
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="Crawling Module Layer",
        )
        common_layer = lambda_alpha.PythonLayerVersion(
            self,
            "SlackCommonLayer",
            entry="lambda/layer/common_layer",
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="A layer that contains the common functions.",
        )

        # Parameter Storeから各種パラメータ取得
        slack_webhook_url = ssm.StringParameter.from_string_parameter_attributes(
            self, "SlackWebhookURL", parameter_name="/crawling-houses/slack/webhook/url"
        )

        if is_use_spreadsheet:
            spreadsheet_id = ssm.StringParameter.from_string_parameter_attributes(
                self, "SpreadsheetID", parameter_name="/crawling-houses/spreadsheet/id"
            )

        crawling_lambda = _lambda.Function(
            self,
            "CrawlingHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            memory_size=256,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("./lambda/crawling_batch"),
            timeout=Duration.seconds(200),
            layers=[crawling_layer, common_layer],
            environment={
                "SLACK_WEBHOOK_URL": slack_webhook_url.string_value,
                "SPREADSHEET_ID": spreadsheet_id.string_value if is_use_spreadsheet else "",
                "TARGET_SLACK_CHANNEL": "#reaction-test",  # TODO #の後ろにSlackのチャンネル名を記載してください
                "TARGET_SHEET_NAME": "Crawler Property Results",
                "DYNAMODB_TABLE_NAME": table.table_name,
                "IS_USE_SPREADSHEET": str(is_use_spreadsheet),  # NOTE trueにするとスプレッドシートに書き込みます
            },
        )

        """
        Permissions
        """
        table.grant_read_write_data(crawling_lambda)

        crawling_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/crawling-houses/google/credentials"],
            )
        )
