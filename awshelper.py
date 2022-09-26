import boto3

_clients = {}
_functions = {}
_session = None


# the last two keys should both be None or both be non-None
def _get_client(client_type, region):
    if _session is None:
        raise ValueError("Session has not been initialized")
    return _session.client(client_type, region_name=region)

NON_PAGINATED_METHODS = [ "describe_load_balancer_attributes"
    , "describe_addresses"
    , "describe_availability_zones"
    , "describe_customer_gateways"
    , "describe_target_health"
    , "describe_vpn_connections"
    , "describe_vpn_gateways"
    , "describe_elasticsearch_domains"
    , "search_transit_gateway_routes"
    ]

def _aws_response(region, cli_name, cli_method, args_dict):
    # See https://boto3.amazonaws.com/v1/documentation/api/latest/guide/paginators.html
    # also https://stackoverflow.com/questions/39201093/how-to-use-boto3-pagination on subtleties
    client = _clients[region][cli_name]
    can_paginate = cli_method not in NON_PAGINATED_METHODS
    if can_paginate:
        paginator = client.get_paginator(cli_method)
        page_iterator = paginator.paginate(**args_dict)
        response = page_iterator.build_full_result()
        # Allegedly boto3 will throw an exception if it encounters an error,
        # so no need to explicitly check.
        return response
    else:
        fun = getattr(client, cli_method)
        response = fun(**args_dict)
        metadata = response["ResponseMetadata"]
        if "HTTPStatusCode" not in metadata or metadata["HTTPStatusCode"] != 200:
            raise IOError("Unexpected status code " + metadata.get("HTTPStatusCode", None))
        response.pop("ResponseMetadata")
        return response


def aws_get_config(region):
    print("Querying region: ", region)
    config = {}
    for key in _functions[region]:
        (cli_name, cli_method, args_dict) = _functions[region][key]
        try:
            response = _aws_response(region, cli_name, cli_method, args_dict)
        except Exception as e:
            print("Exception getting {} for {}: {}".format(key, region, e))
            continue
        config[key] = response
        if key == "TransitGatewayRouteTables":
            _aws_get_route_table_details(region, "ec2", config, response["TransitGatewayRouteTables"])
        if key == "LoadBalancers":
            _aws_get_load_balancer_details(region, "elbv2", config, response["LoadBalancers"])
        if key == "TargetGroups":
            _aws_get_elbv2_target_health(region, "elbv2", config, response["TargetGroups"])
    return config


import json


def _aws_get_load_balancer_details(region, client, config, load_balancers):
    listeners = []
    attributes = []
    for load_balancer in load_balancers:
        lb_arn = load_balancer["LoadBalancerArn"]
        try:
            response = _aws_response(region, client, "describe_listeners", dict(LoadBalancerArn=lb_arn))
            response["LoadBalancerArn"] = lb_arn
            listeners.append(response)
        except Exception as e:
            print(
                "Exception getting load balancer listeners for {} with arn {}: {}".format(
                    load_balancer["LoadBalancerName"],
                    lb_arn, e))

        try:
            response = _aws_response(region, client, "describe_load_balancer_attributes", dict(LoadBalancerArn=lb_arn))
            response["LoadBalancerArn"] = lb_arn
            attributes.append(response)
        except Exception as e:
            print(
                "Exception getting load balancer attributes for {} with arn {}: {}".format(
                    load_balancer["LoadBalancerName"],
                    lb_arn, e))

    config["LoadBalancerListeners"] = {"LoadBalancerListeners": listeners}
    config["LoadBalancerAttributes"] = {"LoadBalancerAttributes" : attributes}


def _aws_get_elbv2_target_health(region, client, config, target_groups):
    healths = []
    for target_group in target_groups:
        tg_arn = target_group["TargetGroupArn"]
        try:
            response = _aws_response(region, client, "describe_target_health", dict(TargetGroupArn=tg_arn))
            response["TargetGroupArn"] = tg_arn
            healths.append(response)
        except Exception as e:
            print(
                "Exception getting target health for target group {} with Arn {}: {}".format(
                    target_group["TargetGroupName"], tg_arn, e))

    config["LoadBalancerTargetHealth"] = {"LoadBalancerTargetHealth": healths}


def _aws_get_route_table_details(region, client, config, route_tables):
    static_routes = []
    propogations = []
    for table in route_tables:
        table_id = table["TransitGatewayRouteTableId"]

        try:
            propogations_response = _aws_response(region, client, "get_transit_gateway_route_table_propagations",
                                                  dict(TransitGatewayRouteTableId=table_id))
            propogations_response["TransitGatewayRouteTableId"] = table_id
            propogations.append(propogations_response)
        except Exception as e:
            print("Exception getting Propagations for {}: {}".format(table_id, e))

        try:
            static_routes_response = _aws_response(region, client, "search_transit_gateway_routes",
                                                   dict(TransitGatewayRouteTableId=table_id,
                                                        Filters=[{"Name": "type", "Values": ["static"]}]))
            if static_routes_response['AdditionalRoutesAvailable']:
                raise IOError("Could not fetch all static routes for " + table_id)
            static_routes_response["TransitGatewayRouteTableId"] = table_id
            static_routes.append(static_routes_response)
        except Exception as e:
            print("Exception getting Static routes for {}: {}".format(table_id, e))

    config["TransitGatewayPropagations"] = {"TransitGatewayPropagations": propogations}
    config["TransitGatewayStaticRoutes"] = {"TransitGatewayStaticRoutes": static_routes}


def aws_get_regions():
    return _clients.keys()


def aws_init(regions=None, vpc_ids=None, skip_data=None, profile=None):
    global _session, _clients, _functions

    _session = boto3.session.Session(profile_name=profile)

    if regions is None or len(regions) == 0:
        ec2_client = _get_client('ec2', "us-west-1")
        response = ec2_client.describe_regions()
        regions_to_get = [region["RegionName"] for region in response["Regions"]]
    else:
        regions_to_get = regions

    if vpc_ids is None or len(vpc_ids) == 0:
        vpc_filter = []
        attachment_vpc_filter = []
    else:
        vpc_filter = [{'Name': "vpc-id", 'Values': vpc_ids}]
        attachment_vpc_filter = [{'Name': "attachment.vpc-id", 'Values': vpc_ids}]

    for region in regions_to_get:
        print("Initializing region: ", region)
        _clients[region] = {}

        ec2_client = _get_client("ec2", region)
        _clients[region]["ec2"] = ec2_client

        _functions[region] = {}
        _functions[region]["Addresses"] = ("ec2", "describe_addresses", dict())
        _functions[region]["AvailabilityZones"] = ("ec2", "describe_availability_zones", dict())
        _functions[region]["ClassicLinkInstances"] = (
            "ec2", "describe_classic_link_instances", dict(Filters=vpc_filter))
        _functions[region]["CustomerGateways"] = ("ec2", "describe_customer_gateways", dict())
        _functions[region]["DhcpOptions"] = ("ec2", "describe_dhcp_options", dict())
        _functions[region]["Hosts"] = ("ec2", "describe_hosts", dict())
        _functions[region]["InstanceStatuses"] = ("ec2", "describe_instance_status", dict())
        _functions[region]["InternetGateways"] = (
            "ec2", "describe_internet_gateways", dict(Filters=attachment_vpc_filter))
        _functions[region]["MovingAddressStatuses"] = ("ec2", "describe_moving_addresses", dict())
        _functions[region]["NatGateways"] = ("ec2", "describe_nat_gateways", dict(Filters=vpc_filter))
        _functions[region]["NetworkAcls"] = ("ec2", "describe_network_acls", dict(Filters=vpc_filter))
        _functions[region]["NetworkInterfaces"] = ("ec2", "describe_network_interfaces", dict(Filters=vpc_filter))
        _functions[region]["PlacementGroups"] = ("ec2", "describe_placement_groups", dict())
        _functions[region]["PrefixLists"] = ("ec2", "describe_prefix_lists", dict())
        _functions[region]["Reservations"] = ("ec2", "describe_instances", dict(Filters=vpc_filter))
        _functions[region]["RouteTables"] = ("ec2", "describe_route_tables", dict(Filters=vpc_filter))
        _functions[region]["SecurityGroups"] = ("ec2", "describe_security_groups", dict(Filters=vpc_filter))
        _functions[region]["Subnets"] = ("ec2", "describe_subnets", dict(Filters=vpc_filter))
        _functions[region]["Tags"] = ("ec2", "describe_tags", dict())
        _functions[region]["TransitGatewayAttachments"] = ("ec2", "describe_transit_gateway_attachments", dict())
        _functions[region]["TransitGatewayRouteTables"] = ("ec2", "describe_transit_gateway_route_tables", dict())
        _functions[region]["TransitGatewayVpcAttachments"] = (
            "ec2", "describe_transit_gateway_vpc_attachments", dict(Filters=vpc_filter))
        _functions[region]["TransitGateways"] = ("ec2", "describe_transit_gateways", dict())
        _functions[region]["VpcEndpoints"] = ("ec2", "describe_vpc_endpoints", dict(Filters=vpc_filter))
        _functions[region]["VpcPeeringConnections"] = ("ec2", "describe_vpc_peering_connections", dict())
        _functions[region]["Vpcs"] = ("ec2", "describe_vpcs", dict(Filters=vpc_filter))
        _functions[region]["VpcClassicLink"] = ("ec2", "describe_vpc_classic_link", dict())
        _functions[region]["VpcClassicLinkDnsSupport"] = ("ec2", "describe_vpc_classic_link_dns_support", dict())
        _functions[region]["VpnConnections"] = ("ec2", "describe_vpn_connections", dict())
        _functions[region]["VpnGateways"] = ("ec2", "describe_vpn_gateways", dict(Filters=attachment_vpc_filter))

        # get all elasticsearch domain names for this account (VPC based filtering is not supported yet)
        es_client = _get_client('es', region)
        _clients[region]["es"] = es_client
        domain_names = es_client.list_domain_names()
        _functions[region]["ElasticsearchDomains"] = ("es", "describe_elasticsearch_domains", dict(
            DomainNames=[domainEntry["DomainName"] for domainEntry in domain_names["DomainNames"]]))

        # get all RDS instances (VPC based filtering is not supported yet)
        rds_client = _get_client('rds', region)
        _clients[region]["rds"] = rds_client
        _functions[region]["RdsInstances"] = ("rds", "describe_db_instances", dict())

        elbv2_client = _get_client('elbv2', region)
        _clients[region]["elbv2"] = elbv2_client
        _functions[region]["LoadBalancers"] = ("elbv2", "describe_load_balancers", dict())
        _functions[region]["TargetGroups"] = ("elbv2", "describe_target_groups", dict())

        if skip_data is not None:
            for key in skip_data:
                _functions[region].pop(key)


def aws_test_access(profile=None):
    try:
        session = boto3.session.Session(profile_name=profile)
        client = session.client("ec2", "us-west-1")
        client.describe_regions()
        print("You have access to AWS!\n")
    except Exception as e:
        print("You may not have access. Exception while accessing AWS: {}".format(e))
